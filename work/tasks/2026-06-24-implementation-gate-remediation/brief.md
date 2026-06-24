# Implementation Gate Remediation Brief

## Goal

Address verified implementation-gate review findings that can block the next push -> staging -> P0 manual validation path.

## Scope

- Make the frontend wait for asynchronous schedule generation completion instead of reading `/result` once after enqueue.
- Ensure worker executor failures leave a terminal failed ScheduleRun state.
- Move recalculation execution onto the same queue/worker path as initial generation, unless existing contracts make that unsafe.
- Reduce Railway worker deployment ambiguity with explicit configuration/documentation.
- Update release checklist drift introduced by completed Redis worker and 100-person baseline work.
- Address second-check P2 stale artifact contract for `/result` while a recalculation is queued/running.

## Non-Goals

- Do not push to GitHub.
- Do not deploy Railway/staging.
- Do not run P0 manual staging validation.
- Do not implement full authentication in this pass; document it as a release/public-staging gate because it is a broader product/security decision.
- Do not touch unrelated existing unstaged review or memory files.

## Success Criteria

- Frontend P0 creation/recalculation flow can reach completed artifacts after a queued run finishes.
- Worker executor exceptions mark the run failed with diagnostic error metadata and do not leave it stuck in running/queued.
- Recalculation requests enqueue work and return a queued state consistently with initial generation.
- Railway worker start command is explicit enough to avoid accidentally running the API process for the worker service.
- Release checklist reflects current completed hardening and remaining public-release blockers.
- Recalculating `queued`/`running` result responses do not expose previous persisted artifacts as if they were the new result.

## Verification Plan

- Add or update focused backend tests before implementation where behavior changes.
- Add a frontend test or build-level validation for async polling when the existing frontend test harness supports it; otherwise validate with `npm run build` and document the gap.
- Run targeted pytest files after each backend change.
- Run full `python -m pytest -q`, frontend `npm run build`, and `git diff --check` before completion.
