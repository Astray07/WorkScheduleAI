from __future__ import annotations

from datetime import date
import hashlib
import json
import math
import os
import re
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.api.security import ADMIN_ROLES, READ_ROLES, require_roles
from work_schedule_ai.db.models import (
    Organization,
    RagDocument,
    RagDocumentChunk,
    RagQueryAudit,
    utc_now,
)
from work_schedule_ai.llm.grounding import (
    RetrievedDocumentChunk,
    RagGroundingResult,
    SourceType,
    build_grounded_explanation_context,
)


router = APIRouter(prefix="/organizations", tags=["rag"])


class RagChunkEmbedding(BaseModel):
    model: str = Field(min_length=1, max_length=120)
    vector: list[float] = Field(min_length=1, max_length=4096)


class RagDocumentIngestRequest(BaseModel):
    source_type: SourceType
    document_title: str = Field(min_length=1, max_length=200)
    checked_at: date
    chunks: list[Annotated[str, Field(min_length=1, max_length=2000)]] = Field(
        min_length=1,
        max_length=50,
    )
    embeddings: list[RagChunkEmbedding] | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def validate_embeddings_match_chunks(self):
        if self.embeddings is not None and len(self.embeddings) != len(self.chunks):
            raise ValueError("embeddings length must match chunks length")
        return self


class RagDocumentResponse(BaseModel):
    id: str
    organization_id: str
    source_type: str
    document_title: str
    checked_at: date
    chunk_count: int


class RagDocumentListResponse(BaseModel):
    organization_id: str
    documents: list[RagDocumentResponse]


class RagQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    purpose: str = Field(min_length=1, max_length=80)
    query_embedding: RagChunkEmbedding | None = None


@router.post(
    "/{organization_id}/rag/documents",
    response_model=RagDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_rag_document(
    organization_id: str,
    request: RagDocumentIngestRequest,
    db_session: Session = Depends(get_db_session),
) -> RagDocumentResponse:
    require_roles(db_session, ADMIN_ROLES)
    _get_organization_or_404(organization_id, db_session)
    document = RagDocument(
        id=_new_id("rag_doc"),
        organization_id=organization_id,
        source_type=request.source_type,
        document_title=request.document_title,
        checked_at=request.checked_at,
        content_hash=_stable_hash(
            {
                "title": request.document_title,
                "checked_at": request.checked_at.isoformat(),
                "chunks": request.chunks,
            }
        ),
        created_at=utc_now(),
    )
    db_session.add(document)
    db_session.flush()
    for index, chunk in enumerate(request.chunks):
        embedding = request.embeddings[index] if request.embeddings is not None else None
        db_session.add(
            RagDocumentChunk(
                id=_new_id("rag_chunk"),
                organization_id=organization_id,
                document_id=document.id,
                chunk_index=index,
                excerpt=chunk,
                embedding_model=embedding.model if embedding is not None else None,
                embedding_dimensions=(
                    len(embedding.vector) if embedding is not None else None
                ),
                embedding_vector_json=(
                    json.dumps(embedding.vector, ensure_ascii=False)
                    if embedding is not None
                    else None
                ),
                embedding_content_hash=(
                    _stable_hash(
                        {
                            "chunk": chunk,
                            "model": embedding.model,
                        }
                    )
                    if embedding is not None
                    else None
                ),
            )
        )
    db_session.commit()
    return RagDocumentResponse(
        id=document.id,
        organization_id=organization_id,
        source_type=document.source_type,
        document_title=document.document_title,
        checked_at=document.checked_at,
        chunk_count=len(request.chunks),
    )


@router.get(
    "/{organization_id}/rag/documents",
    response_model=RagDocumentListResponse,
)
def list_rag_documents(
    organization_id: str,
    db_session: Session = Depends(get_db_session),
) -> RagDocumentListResponse:
    require_roles(db_session, READ_ROLES)
    _get_organization_or_404(organization_id, db_session)
    rows = db_session.execute(
        select(RagDocument, func.count(RagDocumentChunk.id))
        .join(RagDocumentChunk, RagDocumentChunk.document_id == RagDocument.id)
        .where(
            RagDocument.organization_id == organization_id,
            RagDocumentChunk.organization_id == organization_id,
        )
        .group_by(
            RagDocument.id,
            RagDocument.organization_id,
            RagDocument.source_type,
            RagDocument.document_title,
            RagDocument.checked_at,
            RagDocument.content_hash,
            RagDocument.created_at,
        )
        .order_by(RagDocument.checked_at.desc(), RagDocument.document_title)
    ).all()
    return RagDocumentListResponse(
        organization_id=organization_id,
        documents=[
            _document_response(document, chunk_count=chunk_count)
            for document, chunk_count in rows
        ],
    )


@router.delete(
    "/{organization_id}/rag/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_rag_document(
    organization_id: str,
    document_id: str,
    db_session: Session = Depends(get_db_session),
) -> Response:
    require_roles(db_session, ADMIN_ROLES)
    _get_organization_or_404(organization_id, db_session)
    document = db_session.execute(
        select(RagDocument).where(
            RagDocument.organization_id == organization_id,
            RagDocument.id == document_id,
        )
    ).scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="RagDocument not found")
    db_session.execute(
        delete(RagDocumentChunk).where(
            RagDocumentChunk.organization_id == organization_id,
            RagDocumentChunk.document_id == document_id,
        )
    )
    db_session.delete(document)
    db_session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{organization_id}/rag/query",
    response_model=RagGroundingResult,
)
def query_rag_evidence(
    organization_id: str,
    request: RagQueryRequest,
    db_session: Session = Depends(get_db_session),
) -> RagGroundingResult:
    require_roles(db_session, READ_ROLES)
    _get_organization_or_404(organization_id, db_session)
    chunks, retrieval_mode = _retrieve_chunks(
        organization_id,
        request.query,
        db_session,
        query_embedding=request.query_embedding,
    )
    grounding = build_grounded_explanation_context(
        organization_id=organization_id,
        retrieved_chunks=chunks,
    )
    grounding = grounding.model_copy(update={"retrieval_mode": retrieval_mode})
    db_session.add(
        RagQueryAudit(
            id=_new_id("rag_audit"),
            organization_id=organization_id,
            purpose=request.purpose,
            query_hash=_stable_hash({"query": request.query}),
            result_count=len(grounding.evidence),
            safety_notes_json=json.dumps(
                grounding.safety_notes,
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
    )
    db_session.commit()
    return grounding


def _retrieve_chunks(
    organization_id: str,
    query: str,
    db_session: Session,
    *,
    query_embedding: RagChunkEmbedding | None = None,
) -> tuple[list[RetrievedDocumentChunk], str]:
    query_terms = _query_terms(query)
    retrieval_mode = (
        "hybrid"
        if query_embedding is not None and _hybrid_retrieval_enabled()
        else "keyword"
    )
    rows = db_session.execute(
        select(RagDocument, RagDocumentChunk)
        .join(RagDocumentChunk, RagDocumentChunk.document_id == RagDocument.id)
        .where(
            RagDocument.organization_id == organization_id,
            RagDocumentChunk.organization_id == organization_id,
        )
        .order_by(RagDocument.created_at.desc(), RagDocumentChunk.chunk_index)
    ).all()
    retrieved: list[RetrievedDocumentChunk] = []
    for document, chunk in rows:
        keyword_score = _keyword_score(
            query_terms=query_terms,
            query=query,
            document_title=document.document_title,
            excerpt=chunk.excerpt,
        )
        score = keyword_score
        if retrieval_mode == "hybrid":
            vector_score = _vector_score(
                query_embedding=query_embedding,
                chunk=chunk,
            )
            score = _hybrid_score(
                keyword_score=keyword_score,
                vector_score=vector_score,
            )
        if score <= 0:
            continue
        retrieved.append(
            RetrievedDocumentChunk(
                organization_id=organization_id,
                source_type=document.source_type,
                document_id=document.id,
                document_title=document.document_title,
                chunk_id=chunk.id,
                excerpt=chunk.excerpt,
                checked_at=document.checked_at,
                retrieval_score=score,
            )
        )
    return (
        sorted(retrieved, key=lambda item: item.retrieval_score, reverse=True),
        retrieval_mode,
    )


def _query_terms(query: str) -> set[str]:
    return {
        term.strip().lower()
        for term in re.split(r"[\s,.;:!?()\[\]{}\"'“”‘’]+", query)
        if term.strip()
    }


def _keyword_score(
    *,
    query_terms: set[str],
    query: str,
    document_title: str,
    excerpt: str,
) -> float:
    if not query_terms:
        return 0.0
    normalized_title = document_title.lower()
    normalized_excerpt = excerpt.lower()
    normalized = f"{normalized_title} {normalized_excerpt}"
    matches = sum(1 for term in query_terms if term in normalized)
    if matches == 0:
        return 0.0
    title_matches = sum(1 for term in query_terms if term in normalized_title)
    phrase_boost = 0.1 if query.strip().lower() in normalized else 0.0
    title_boost = 0.05 if title_matches else 0.0
    return min(
        1.0,
        0.45 + (matches / len(query_terms)) * 0.5 + phrase_boost + title_boost,
    )


def _vector_score(
    *,
    query_embedding: RagChunkEmbedding | None,
    chunk: RagDocumentChunk,
) -> float | None:
    if query_embedding is None:
        return None
    if chunk.embedding_model != query_embedding.model:
        return None
    if chunk.embedding_vector_json is None:
        return None
    try:
        chunk_vector = json.loads(chunk.embedding_vector_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(chunk_vector, list):
        return None
    if len(chunk_vector) != len(query_embedding.vector):
        return None
    if chunk.embedding_dimensions is not None and chunk.embedding_dimensions != len(chunk_vector):
        return None
    try:
        values = [float(value) for value in chunk_vector]
    except (TypeError, ValueError):
        return None
    query_values = [float(value) for value in query_embedding.vector]
    chunk_norm = math.sqrt(sum(value * value for value in values))
    query_norm = math.sqrt(sum(value * value for value in query_values))
    if chunk_norm == 0 or query_norm == 0:
        return None
    cosine = sum(
        query_value * chunk_value
        for query_value, chunk_value in zip(query_values, values, strict=True)
    ) / (query_norm * chunk_norm)
    return max(0.0, min(1.0, (cosine + 1.0) / 2.0))


def _hybrid_score(*, keyword_score: float, vector_score: float | None) -> float:
    if vector_score is None:
        return round(keyword_score * 0.25, 6)
    return round(min(1.0, vector_score * 0.75 + keyword_score * 0.25), 6)


def _hybrid_retrieval_enabled() -> bool:
    return os.environ.get("WORKSCHEDULEAI_RAG_HYBRID_RETRIEVAL") == "1"


def _get_organization_or_404(
    organization_id: str,
    db_session: Session,
) -> Organization:
    organization = db_session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization


def _document_response(document: RagDocument, *, chunk_count: int) -> RagDocumentResponse:
    return RagDocumentResponse(
        id=document.id,
        organization_id=document.organization_id,
        source_type=document.source_type,
        document_title=document.document_title,
        checked_at=document.checked_at,
        chunk_count=chunk_count,
    )


def _stable_hash(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"
