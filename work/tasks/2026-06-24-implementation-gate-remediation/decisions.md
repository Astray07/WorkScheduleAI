# Implementation Gate Remediation Decisions

## Decisions

- Treat frontend polling as a P0 blocker because backend generation is now asynchronous by design.
- Treat worker failed-state persistence as P1 because Redis `BLPOP` removes jobs before execution; a raised exception without state persistence creates operator ambiguity.
- Treat recalculation queueing as P1 consistency work because current inline execution conflicts with the worker split and can reintroduce request-path solver latency.
- Treat authentication as a documented release/public-staging blocker instead of adding a rushed minimal auth layer in this remediation pass.
- Treat queued/running `/result` responses as in-progress state with empty artifacts, even when previous persisted artifacts exist, to avoid stale reads for API consumers.

## Alternatives Considered

- Requeue failed jobs automatically: deferred because retry semantics need to respect `current_attempt_no`, idempotency, and non-deterministic executor failures. Marking failed is the minimal safe behavior for this gate.
- Keep recalculation inline and document it: rejected for now because reviewer feedback identifies it as an inconsistency in the worker split, and the existing queue executor already has the data needed to process recalculation state.
- Add explicit previous-result metadata during recalculation: deferred because the current API schema and frontend only need a clear in-progress contract. Empty artifacts for queued/running is the smallest compatible behavior.
