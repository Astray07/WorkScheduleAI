# RAG Vector And Evaluation Plan

Date: 2026-06-26

## Current Scope

- RAG retrieval remains keyword-first and tenant-scoped by default.
- `rag_document_chunks` can store nullable embedding metadata per chunk:
  - `embedding_model`
  - `embedding_dimensions`
  - `embedding_vector_json`
  - `embedding_content_hash`
- Query responses expose `retrieval_mode="keyword"` by default.
- When `WORKSCHEDULEAI_RAG_HYBRID_RETRIEVAL=1` and the query request supplies `query_embedding`, stored chunk embeddings are combined with keyword scores and responses expose `retrieval_mode="hybrid"`.
- RAG remains read-only with respect to `SchedulePolicy`, warning rules, constraints, and solver inputs.

## Vector Rollout

1. Keep SQLite/local tests on JSON metadata.
2. Add PostgreSQL/pgvector migration only after production DB extension availability is verified.
3. Backfill embeddings per tenant and document version; compare `embedding_content_hash` before reuse.
4. Expand hybrid retrieval from JSON-vector local scoring to PostgreSQL pgvector indexes after extension availability is verified.
5. Add server-side embedding generation/backfill jobs; current query embedding input is an explicit contract, not automatic LLM policy mutation.
6. Keep citation confidence visible and preserve prompt-injection and PII redaction guardrails.

## Evaluation Set

The initial long-running evaluation contract lives in `work_schedule_ai.llm.rag_evaluation`.

Required checks:

- every sample has a stable ID, query, purpose, and expected source IDs;
- retrieval/citation tests score exact expected source ID matches;
- future vector/hybrid retrieval must pass the same evaluation before replacing keyword default;
- hybrid retrieval must stay behind explicit configuration until long-running evaluation is part of CI or release verification;
- no evaluation result may directly mutate solver, schedule policy, warning rules, or constraints.

## Non-Goals

- No automatic policy updates from RAG output.
- No LLM-driven scheduling decisions.
- No legal compliance guarantee from retrieved text.
