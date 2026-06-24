from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator


DEFAULT_FALLBACK_TEXT = "서버 템플릿으로 mock 근무표 설명을 생성했습니다."


class StructuredExplanation(BaseModel):
    summary: str = Field(min_length=1, max_length=120)
    reason_bullets: list[str] = Field(default_factory=list, max_length=3)
    recommended_action_label: str = Field(min_length=1, max_length=80)
    caution_level: Literal["none", "low", "medium", "high"]
    reason_codes: list[str] = Field(default_factory=list)
    proposal_type: str | None = None

    @field_validator("reason_bullets")
    @classmethod
    def validate_reason_bullets(cls, value: list[str]) -> list[str]:
        for bullet in value:
            if len(bullet) > 120:
                raise ValueError("reason bullet cannot exceed 120 characters")
        return value


def fallback_explanation(text: str = DEFAULT_FALLBACK_TEXT) -> dict[str, str | None]:
    return {
        "status": "fallback",
        "text": text,
        "source": "server_template",
    }


def build_anonymized_payload(context: Mapping[str, Any]) -> dict[str, Any]:
    issue = _mapping(context.get("issue"))
    aliases = _RequestAliases()
    excluded_candidates = [
        {
            "employee": aliases.for_candidate(candidate),
            "reason": _reason(candidate),
        }
        for candidate in _sequence_of_mappings(context.get("excluded_candidates"))
    ]
    relational_conflicts = [
        {
            "employees": [
                aliases.for_value(employee_key)
                for employee_key in _employee_keys(conflict)
            ],
            "reason": _reason(conflict),
        }
        for conflict in _sequence_of_mappings(context.get("relational_conflicts"))
    ]
    proposals = [
        _safe_code(proposal.get("type"))
        for proposal in _sequence_of_mappings(context.get("proposals"))
        if proposal.get("type")
    ]
    return {
        "slot_label": "target slot",
        "missing_role": _role_label(issue),
        "issue_type": _safe_code(issue.get("type")).lower(),
        "reason_code": _safe_code(issue.get("reason_code")),
        "missing_count": int(issue.get("missing_count") or 0),
        "loss_level": _loss_level(issue.get("severity")),
        "excluded_candidates": excluded_candidates,
        "relational_conflicts": relational_conflicts,
        "available_relaxations": proposals,
    }


def render_explanation(
    provider_response: Mapping[str, Any] | None,
    *,
    allowed_reason_codes: set[str] | frozenset[str],
    allowed_proposal_types: set[str] | frozenset[str],
    fallback_text: str = DEFAULT_FALLBACK_TEXT,
) -> dict[str, str | None]:
    if provider_response is None:
        return fallback_explanation(fallback_text)

    try:
        output = StructuredExplanation.model_validate(provider_response)
    except ValidationError:
        return fallback_explanation(fallback_text)

    if _distorts_reason_codes(output, allowed_reason_codes):
        return fallback_explanation(fallback_text)
    if _distorts_proposal_type(output, allowed_proposal_types):
        return fallback_explanation(fallback_text)

    return {
        "status": "ready",
        "text": _render_text(output),
        "source": "llm",
    }


def _distorts_reason_codes(
    output: StructuredExplanation,
    allowed_reason_codes: set[str] | frozenset[str],
) -> bool:
    allowed = {_safe_code(value) for value in allowed_reason_codes}
    return any(_safe_code(value) not in allowed for value in output.reason_codes)


def _distorts_proposal_type(
    output: StructuredExplanation,
    allowed_proposal_types: set[str] | frozenset[str],
) -> bool:
    if output.proposal_type is None:
        return False
    allowed = {_safe_code(value) for value in allowed_proposal_types}
    return _safe_code(output.proposal_type) not in allowed


def _render_text(output: StructuredExplanation) -> str:
    parts = [output.summary, *output.reason_bullets, output.recommended_action_label]
    return "\n".join(part for part in parts if part)[:500]


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence_of_mappings(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _employee_keys(conflict: Mapping[str, Any]) -> list[Any]:
    for key in ("employee_ids", "employee_keys", "employees", "employee_names"):
        value = conflict.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return list(value)
    return []


def _reason(item: Mapping[str, Any]) -> str:
    return _safe_code(item.get("reason") or item.get("reason_code") or "UNKNOWN")


def _role_label(issue: Mapping[str, Any]) -> str:
    raw = str(
        issue.get("role_name")
        or issue.get("role_label")
        or issue.get("role")
        or "target_role"
    ).strip()
    normalized = raw.lower()
    if normalized in {"부사수", "assistant", "junior", "role_junior"}:
        return "assistant"
    if normalized in {"사수", "senior", "lead", "role_senior"}:
        return "senior"
    return "target_role"


def _loss_level(value: Any) -> str:
    normalized = str(value or "medium").strip().lower()
    if normalized in {"none", "low", "medium", "high"}:
        return normalized
    return "medium"


def _safe_code(value: Any) -> str:
    text = str(value or "UNKNOWN").strip()
    return "".join(char if char.isalnum() else "_" for char in text).upper()


class _RequestAliases:
    def __init__(self) -> None:
        self._aliases: dict[str, str] = {}

    def for_candidate(self, candidate: Mapping[str, Any]) -> str:
        return self.for_value(
            candidate.get("employee_id")
            or candidate.get("employee_key")
            or candidate.get("employee_name")
            or candidate.get("employee_email")
            or candidate.get("employee_code")
            or len(self._aliases)
        )

    def for_value(self, value: Any) -> str:
        key = str(value)
        if key not in self._aliases:
            self._aliases[key] = f"P{len(self._aliases) + 1}"
        return self._aliases[key]
