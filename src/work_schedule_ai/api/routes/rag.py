from __future__ import annotations

from datetime import date
import hashlib
import json
import re
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
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


class RagDocumentIngestRequest(BaseModel):
    source_type: SourceType
    document_title: str = Field(min_length=1, max_length=200)
    checked_at: date
    chunks: list[Annotated[str, Field(min_length=1, max_length=2000)]] = Field(
        min_length=1,
        max_length=50,
    )


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
        db_session.add(
            RagDocumentChunk(
                id=_new_id("rag_chunk"),
                organization_id=organization_id,
                document_id=document.id,
                chunk_index=index,
                excerpt=chunk,
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
    chunks = _retrieve_chunks(organization_id, request.query, db_session)
    grounding = build_grounded_explanation_context(
        organization_id=organization_id,
        retrieved_chunks=chunks,
    )
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
) -> list[RetrievedDocumentChunk]:
    query_terms = _query_terms(query)
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
        score = _keyword_score(
            query_terms=query_terms,
            query=query,
            document_title=document.document_title,
            excerpt=chunk.excerpt,
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
    return sorted(retrieved, key=lambda item: item.retrieval_score, reverse=True)


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
