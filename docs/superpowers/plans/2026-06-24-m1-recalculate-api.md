# M1 Recalculate API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `POST /organizations/{organization_id}/schedule-runs/{schedule_run_id}/recalculate` for the P0 recalculation step after approving a relaxation proposal.

**Architecture:** Add a small `ScheduleRecalculationRequest` table to record accepted recalculation requests and idempotency keys. Extend the schedule run router so recalculate requires an approved override, increments only `recalculation_count`, keeps `current_attempt_no` unchanged, and makes the deterministic mock result resolve the previously unfilled requirement.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, pytest, SQLite in-memory tests.

---

## File Structure

- Modify: `src/work_schedule_ai/db/models.py` - add `ScheduleRecalculationRequest`.
- Modify: `src/work_schedule_ai/db/__init__.py` - export `ScheduleRecalculationRequest`.
- Create: `alembic/versions/20260624_0005_m1_schedule_recalculations.py` - create recalculation request table.
- Modify: `tests/db/test_domain_models.py` - add idempotency uniqueness coverage.
- Modify: `tests/db/test_alembic_migrations.py` - expect recalculation table, unique constraint, indexes, and head revision.
- Modify: `tests/api/test_schedule_runs_api.py` - add recalculate API tests.
- Modify: `src/work_schedule_ai/api/routes/schedule_runs.py` - add recalculate schema/endpoint and mock result resolution.
- Create: `work/tasks/2026-06-24-m1-recalculate-api/*.md` - task harness notes.

## Task 1: Write Failing DB And API Tests

**Files:**
- Modify: `tests/db/test_domain_models.py`
- Modify: `tests/db/test_alembic_migrations.py`
- Modify: `tests/api/test_schedule_runs_api.py`

- [x] **Step 1: Add domain model test**

Test case:

- duplicate `(organization_id, schedule_run_id, idempotency_key)` recalculation request is rejected.

- [x] **Step 2: Add Alembic test coverage**

Assertions:

- `schedule_recalculation_requests` exists after `upgrade head`.
- named unique constraint `uq_schedule_recalculations_run_idempotency_key` exists.
- indexes include `ix_schedule_recalculations_organization_id` and `ix_schedule_recalculations_schedule_run_id`.
- `alembic_version` is `20260624_0005`.

- [x] **Step 3: Add API tests**

Test cases:

- approved proposal then recalculate returns 202, increments `recalculation_count` to 1, keeps `current_attempt_no=1`, and records one recalculation request.
- result after recalculation has no unfilled issues and has 14 assignments for the 7-day, 2-role mock grid.
- recalculate without an approved override returns 409 and does not increment.
- same `Idempotency-Key` returns the existing count and records only one recalculation request.
- fourth recalculation returns 409 and keeps `recalculation_count=3`.

- [x] **Step 4: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py tests/api/test_schedule_runs_api.py -q
```

Expected: FAIL because `ScheduleRecalculationRequest` and the recalculate endpoint are not implemented yet.

## Task 2: Implement Model And Migration

**Files:**
- Modify: `src/work_schedule_ai/db/models.py`
- Modify: `src/work_schedule_ai/db/__init__.py`
- Create: `alembic/versions/20260624_0005_m1_schedule_recalculations.py`

- [x] **Step 1: Add `ScheduleRecalculationRequest` model**

Fields: `id`, `organization_id`, `schedule_run_id`, `idempotency_key`, `reason`, `recalculation_count`, `created_at`.

Constraints:

- `(organization_id, schedule_run_id, idempotency_key)` is unique.
- `recalculation_count` must be between 1 and 3.

- [x] **Step 2: Add Alembic revision**

Create the table with named constraints and indexes.

- [x] **Step 3: Run DB tests**

Run:

```powershell
python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py -q
```

Expected: DB model and migration tests pass.

## Task 3: Implement Recalculate API

**Files:**
- Modify: `src/work_schedule_ai/api/routes/schedule_runs.py`

- [x] **Step 1: Add request schema**

Use `reason: str` with max length 500.

- [x] **Step 2: Validate run and prerequisites**

Rules:

- schedule run must exist in the organization, otherwise 404.
- at least one `OverrideApproval` must exist for the run, otherwise 409.
- `recalculation_count >= 3` returns 409 and does not increment.
- repeated `Idempotency-Key` returns current response without a second increment.

- [x] **Step 3: Persist accepted recalculation**

Increment `recalculation_count` by 1, keep `current_attempt_no` unchanged, update `updated_at`, create `recalc_<uuid>` record, and return `ScheduleRunResponse` with 202.

- [x] **Step 4: Resolve mock issue after recalculation**

If the run has an approved override and `recalculation_count > 0`, the mock result builder should not create the unfilled issue and should assign all 14 requirements.

- [x] **Step 5: Run API tests**

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

Record RED/GREEN/full test results in `work/tasks/2026-06-24-m1-recalculate-api/verification.md` and update handoff state.

- [x] **Step 4: Commit changes**

Run:

```powershell
git add src tests alembic docs/superpowers/plans/2026-06-24-m1-recalculate-api.md work/tasks/2026-06-24-m1-recalculate-api
git commit -m "feat: add schedule recalculation api"
```
