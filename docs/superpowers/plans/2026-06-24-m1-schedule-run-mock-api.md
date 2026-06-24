# M1 ScheduleRun Mock API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `POST /organizations/{organization_id}/schedule-runs`, `GET /schedule-runs/{id}`, and `GET /schedule-runs/{id}/result` with a deterministic mock result for the P0 1-week schedule flow.

**Architecture:** Add persisted `ScheduleRun` and `ScheduleInputSnapshot` tables, then expose one focused FastAPI router. The create endpoint records the execution request and input snapshot, returns a completed mock run synchronously, and the result endpoint generates deterministic UI payloads from existing employees/roles without invoking OR-Tools or LLM.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, pytest, SQLite in-memory tests.

---

## File Structure

- Modify: `src/work_schedule_ai/db/models.py` - add `ScheduleRun` and `ScheduleInputSnapshot`.
- Modify: `src/work_schedule_ai/db/__init__.py` - export schedule models.
- Create: `alembic/versions/20260624_0003_m1_schedule_runs.py` - create schedule run and input snapshot tables.
- Modify: `tests/db/test_domain_models.py` - add status/recalculation constraint coverage.
- Modify: `tests/db/test_alembic_migrations.py` - expect new tables, constraints, indexes, and head revision.
- Create: `tests/api/test_schedule_runs_api.py` - TDD API tests for create/get/result/validation/idempotency.
- Create: `src/work_schedule_ai/api/routes/schedule_runs.py` - schedule run router and mock result builder.
- Modify: `src/work_schedule_ai/api/app.py` - include schedule run router.
- Create: `work/tasks/2026-06-24-m1-schedule-run-mock-api/*.md` - task harness notes.

## Task 1: Write Failing DB And API Tests

**Files:**
- Modify: `tests/db/test_domain_models.py`
- Modify: `tests/db/test_alembic_migrations.py`
- Create: `tests/api/test_schedule_runs_api.py`

- [x] **Step 1: Add domain model tests**

Test cases:

- invalid `ScheduleRun.status` is rejected by `ck_schedule_runs_status`.
- `recalculation_count > 3` is rejected by `ck_schedule_runs_recalculation_count`.

- [x] **Step 2: Add Alembic tests**

Assertions:

- `schedule_runs` and `schedule_input_snapshots` exist after `upgrade head`.
- named constraints include `ck_schedule_runs_status`, `ck_schedule_runs_recalculation_count`, and `uq_schedule_runs_organization_idempotency_key`.
- indexes include `ix_schedule_runs_organization_id`, `ix_schedule_runs_organization_period`, `ix_schedule_input_snapshots_organization_id`, and `ix_schedule_input_snapshots_schedule_run_id`.
- `alembic_version` is `20260624_0003`.

- [x] **Step 3: Add API tests**

Test cases:

- valid one-week request returns 202, persists one run and one input snapshot, and sets `current_attempt_no=1`, `recalculation_count=0`.
- same `Idempotency-Key` returns the existing run instead of creating another row.
- period longer than 31 days returns 422 and writes nothing.
- `GET /schedule-runs/{id}` returns the persisted run.
- `GET /schedule-runs/{id}/result` returns 7 slots, requirements, assignments, one soft unfilled issue, one suggested relaxation proposal, `publication=null`, and server-template LLM fallback.

- [x] **Step 4: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py tests/api/test_schedule_runs_api.py -q
```

Expected: FAIL because `ScheduleRun`, `ScheduleInputSnapshot`, and the route are not implemented yet.

## Task 2: Implement Model And Migration

**Files:**
- Modify: `src/work_schedule_ai/db/models.py`
- Modify: `src/work_schedule_ai/db/__init__.py`
- Create: `alembic/versions/20260624_0003_m1_schedule_runs.py`

- [x] **Step 1: Add `ScheduleRun` model**

Fields: `id`, `organization_id`, `period_start`, `period_end`, `template`, `deterministic_mode`, `timeout_seconds`, `status`, `solver_status`, `solution_quality`, `current_attempt_no`, `recalculation_count`, `input_snapshot_hash`, `idempotency_key`, timestamps.

Constraints:

- `ck_schedule_runs_status`
- `ck_schedule_runs_solver_status`
- `ck_schedule_runs_solution_quality`
- `ck_schedule_runs_template`
- `ck_schedule_runs_period_order`
- `ck_schedule_runs_timeout_seconds`
- `ck_schedule_runs_current_attempt_no`
- `ck_schedule_runs_recalculation_count`
- `uq_schedule_runs_organization_idempotency_key`

- [x] **Step 2: Add `ScheduleInputSnapshot` model**

Fields: `id`, `organization_id`, `schedule_run_id`, `snapshot_hash`, `payload_json`, `storage_uri`, `created_at`.

- [x] **Step 3: Add Alembic revision**

Create both tables with named constraints and indexes.

- [x] **Step 4: Run DB tests**

Run:

```powershell
python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py -q
```

Expected: DB model and migration tests pass.

## Task 3: Implement ScheduleRun API And Mock Result

**Files:**
- Create: `src/work_schedule_ai/api/routes/schedule_runs.py`
- Modify: `src/work_schedule_ai/api/app.py`

- [x] **Step 1: Add request/response schemas**

Use `date` for period fields, `Literal` enums for contract values, and local Pydantic models for progress, score summary, issue, proposal, slot, requirement, assignment, and result.

- [x] **Step 2: Validate request**

Rules:

- organization must exist, otherwise 404.
- inclusive period length must be 1-31 days.
- `timeout_seconds` must stay within 1-120.

- [x] **Step 3: Persist run and snapshot**

For the M1 mock API, create a run with `status=succeeded`, `solver_status=not_started`, `solution_quality=feasible_not_proven_optimal`, `current_attempt_no=1`, `recalculation_count=0`, and a deterministic snapshot hash.

- [x] **Step 4: Implement idempotency**

If the same organization sends the same `Idempotency-Key`, return the existing run without inserting a duplicate.

- [x] **Step 5: Implement result builder**

Generate one day slot per inclusive date. Generate one requirement per role per slot. Assign employees round-robin, but leave the first `부사수` requirement unassigned and represent it as `ScheduleIssue` plus one suggested `approve_time_off_override` proposal.

- [x] **Step 6: Run API tests**

Run:

```powershell
python -m pytest tests/api/test_schedule_runs_api.py -q
```

Expected: all schedule run API tests pass.

## Task 4: Verify, Document, And Commit

- [x] **Step 1: Run focused and full tests**

Run:

```powershell
python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py tests/api/test_schedule_runs_api.py -q
python -m pytest -q
```

Expected: all tests pass.

- [x] **Step 2: Run diff check**

Run:

```powershell
git diff --check
```

Expected: no whitespace errors.

- [x] **Step 3: Update harness documents**

Record RED/GREEN/full test results in `work/tasks/2026-06-24-m1-schedule-run-mock-api/verification.md` and update handoff state.

- [x] **Step 4: Commit changes**

Run:

```powershell
git add src tests alembic docs/superpowers/plans/2026-06-24-m1-schedule-run-mock-api.md work/tasks/2026-06-24-m1-schedule-run-mock-api
git commit -m "feat: add schedule run mock api"
```
