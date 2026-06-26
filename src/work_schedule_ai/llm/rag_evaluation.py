from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RagEvaluationSample:
    id: str
    query: str
    purpose: str
    expected_source_ids: list[str]


@dataclass(frozen=True)
class RagCitationEvaluationResult:
    sample_id: str
    matched: bool
    matched_source_ids: list[str]
    missing_source_ids: list[str]


DEFAULT_RAG_EVALUATION_SAMPLES = (
    RagEvaluationSample(
        id="rest-after-night-shift",
        query="야간 근무 다음 날 휴식 기준을 설명해줘",
        purpose="schedule_explanation",
        expected_source_ids=["policy-rest-minimum-11h"],
    ),
    RagEvaluationSample(
        id="weekly-hours-review",
        query="주간 근무시간 초과 warning 근거를 알려줘",
        purpose="schedule_explanation",
        expected_source_ids=["compliance-weekly-hours-review"],
    ),
    RagEvaluationSample(
        id="employee-request-approval",
        query="직원 요청이 승인되면 solver input에 어떻게 반영돼?",
        purpose="schedule_explanation",
        expected_source_ids=["ops-employee-request-approval-flow"],
    ),
)


def load_default_rag_evaluation_samples() -> list[RagEvaluationSample]:
    return list(DEFAULT_RAG_EVALUATION_SAMPLES)


def evaluate_citation_matches(
    samples: list[RagEvaluationSample],
    retrieved_source_ids_by_sample_id: dict[str, list[str]],
) -> list[RagCitationEvaluationResult]:
    results: list[RagCitationEvaluationResult] = []
    for sample in samples:
        retrieved_source_ids = set(
            retrieved_source_ids_by_sample_id.get(sample.id, [])
        )
        expected_source_ids = set(sample.expected_source_ids)
        matched_source_ids = sorted(expected_source_ids & retrieved_source_ids)
        missing_source_ids = sorted(expected_source_ids - retrieved_source_ids)
        results.append(
            RagCitationEvaluationResult(
                sample_id=sample.id,
                matched=not missing_source_ids,
                matched_source_ids=matched_source_ids,
                missing_source_ids=missing_source_ids,
            )
        )
    return results
