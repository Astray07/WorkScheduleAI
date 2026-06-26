from __future__ import annotations

from work_schedule_ai.llm.rag_evaluation import (
    evaluate_citation_matches,
    load_default_rag_evaluation_samples,
)


def test_default_rag_evaluation_samples_define_expected_sources():
    samples = load_default_rag_evaluation_samples()

    assert len(samples) >= 3
    assert all(sample.query for sample in samples)
    assert all(sample.expected_source_ids for sample in samples)
    assert all(sample.purpose == "schedule_explanation" for sample in samples)


def test_evaluate_citation_matches_scores_expected_sources():
    samples = load_default_rag_evaluation_samples()
    first = samples[0]

    results = evaluate_citation_matches(
        samples,
        {
            first.id: [first.expected_source_ids[0]],
        },
    )

    first_result = next(result for result in results if result.sample_id == first.id)
    assert first_result.matched is True
    assert first_result.matched_source_ids == [first.expected_source_ids[0]]
    assert any(result.matched is False for result in results if result.sample_id != first.id)
