# RAG Vector And Evaluation Plan

Date: 2026-06-26

## Current Scope

- RAG retrieval remains keyword-first and tenant-scoped.
- `rag_document_chunks` can store nullable embedding metadata per chunk:
  - `embedding_model`
  - `embedding_dimensions`
  - `embedding_vector_json`
  - `embedding_content_hash`
- Query responses expose `retrieval_mode="keyword"` so callers do not mistake this for live vector retrieval.
- RAG remains read-only with respect to `SchedulePolicy`, warning rules, constraints, and solver inputs.

## Vector Rollout

1. Keep SQLite/local tests on JSON metadata.
2. Add PostgreSQL/pgvector migration only after production DB extension availability is verified.
3. Backfill embeddings per tenant and document version; compare `embedding_content_hash` before reuse.
4. Add hybrid retrieval behind an explicit server-side config flag.
5. Keep citation confidence visible and preserve prompt-injection and PII redaction guardrails.

## Evaluation Set

The initial long-running evaluation contract lives in `work_schedule_ai.llm.rag_evaluation`.

Required checks:

- every sample has a stable ID, query, purpose, and expected source IDs;
- retrieval/citation tests score exact expected source ID matches;
- future vector/hybrid retrieval must pass the same evaluation before replacing keyword default;
- no evaluation result may directly mutate solver, schedule policy, warning rules, or constraints.

## Non-Goals

- No automatic policy updates from RAG output.
- No LLM-driven scheduling decisions.
- No legal compliance guarantee from retrieved text.
