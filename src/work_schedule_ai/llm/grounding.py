from __future__ import annotations

from collections.abc import Sequence
from datetime import date
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


SourceType = Literal[
    "organization_policy",
    "internal_rule",
    "compliance_guide",
    "approval_history",
    "audit_log",
    "product_document",
]
GroundingStatus = Literal["grounded", "insufficient_evidence"]
ConfidenceLabel = Literal["high", "medium", "low", "insufficient"]


class RetrievedDocumentChunk(BaseModel):
    organization_id: str = Field(min_length=1)
    source_type: SourceType
    document_id: str = Field(min_length=1)
    document_title: str = Field(min_length=1, max_length=200)
    chunk_id: str = Field(min_length=1)
    excerpt: str = Field(min_length=1, max_length=2000)
    checked_at: date
    retrieval_score: float = Field(ge=0, le=1)

    @field_validator(
        "organization_id",
        "document_id",
        "document_title",
        "chunk_id",
        "excerpt",
    )
    @classmethod
    def strip_text_fields(cls, value: str) -> str:
        return value.strip()


class GroundedEvidence(BaseModel):
    source_type: SourceType
    document_id: str
    document_title: str
    chunk_id: str
    excerpt: str
    checked_at: date
    confidence: float = Field(ge=0, le=1)


class RagGroundingResult(BaseModel):
    status: GroundingStatus
    confidence: ConfidenceLabel
    evidence: list[GroundedEvidence]
    safety_notes: list[str]


def build_grounded_explanation_context(
    *,
    organization_id: str,
    retrieved_chunks: Sequence[RetrievedDocumentChunk],
    min_retrieval_score: float = 0.35,
    max_evidence: int = 4,
) -> RagGroundingResult:
    safety_notes: list[str] = []
    evidence: list[GroundedEvidence] = []
    seen_chunk_keys: set[tuple[str, str]] = set()

    for chunk in retrieved_chunks:
        if chunk.organization_id != organization_id:
            _add_note(safety_notes, "cross_tenant_chunk_dropped")
            continue
        if chunk.retrieval_score < min_retrieval_score:
            _add_note(safety_notes, "low_confidence_chunk_dropped")
            continue
        if _contains_prompt_injection(chunk.excerpt):
            _add_note(safety_notes, "prompt_injection_chunk_dropped")
            continue

        chunk_key = (chunk.document_id, chunk.chunk_id)
        if chunk_key in seen_chunk_keys:
            continue
        seen_chunk_keys.add(chunk_key)

        excerpt, redacted = _redact_direct_identifiers(chunk.excerpt)
        if redacted:
            _add_note(safety_notes, "pii_redacted")

        evidence.append(
            GroundedEvidence(
                source_type=chunk.source_type,
                document_id=chunk.document_id,
                document_title=chunk.document_title,
                chunk_id=chunk.chunk_id,
                excerpt=excerpt,
                checked_at=chunk.checked_at,
                confidence=round(chunk.retrieval_score, 3),
            )
        )

    evidence.sort(key=lambda item: (-item.confidence, item.document_id, item.chunk_id))
    evidence = evidence[: max(0, max_evidence)]

    if not evidence:
        _add_note(safety_notes, "insufficient_evidence")
        return RagGroundingResult(
            status="insufficient_evidence",
            confidence="insufficient",
            evidence=[],
            safety_notes=safety_notes,
        )

    return RagGroundingResult(
        status="grounded",
        confidence=_confidence_label(evidence),
        evidence=evidence,
        safety_notes=safety_notes,
    )


def _confidence_label(evidence: Sequence[GroundedEvidence]) -> ConfidenceLabel:
    top_confidence = evidence[0].confidence
    if top_confidence >= 0.75:
        return "high"
    if top_confidence >= 0.55:
        return "medium"
    return "low"


def _contains_prompt_injection(excerpt: str) -> bool:
    normalized = excerpt.lower()
    patterns = (
        "ignore previous instructions",
        "ignore all previous instructions",
        "disregard previous instructions",
        "forget previous instructions",
        "system prompt",
        "developer message",
        "reveal every",
        "bypass",
    )
    return any(pattern in normalized for pattern in patterns)


def _redact_direct_identifiers(excerpt: str) -> tuple[str, bool]:
    redacted = excerpt
    for pattern, token in (
        (re.compile(r"(?<!\d)\d{6}-[1-4]\d{6}(?!\d)"), "[redacted_id]"),
        (
            re.compile(
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
            ),
            "[redacted_email]",
        ),
        (
            re.compile(r"\b(?:\+?82[- ]?)?0\d{1,2}[- ]?\d{3,4}[- ]?\d{4}\b"),
            "[redacted_phone]",
        ),
    ):
        redacted = pattern.sub(token, redacted)
    return redacted, redacted != excerpt


def _add_note(notes: list[str], note: str) -> None:
    if note not in notes:
        notes.append(note)
