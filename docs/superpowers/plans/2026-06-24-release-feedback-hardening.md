# Release Feedback Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans and superpowers:test-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the second review's P0/P1 API hardening gaps for publication immutability, scoped relaxations, manual edit validation, schedule input reproducibility, and baseline PostgreSQL tenant RLS.

**Architecture:** Keep changes surgical in `schedule_runs.py`. Add response/request models for manual validation, use persisted artifacts first, derive generated slot/requirement snapshot payload from existing shift templates, scope time-off overrides to the approved proposal's affected slot and candidate employee, and add PostgreSQL-only RLS migration plus request tenant context setup.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, Alembic-managed current schema, OR-Tools solver path.

---

### Task 1: Regression Tests

**Files:**
- Modify: `tests/api/test_schedule_runs_api.py`

- [x] Add tests for published run recalculation rejection, slot-scoped time-off override, role-shortage manual-review proposal, manual edit validation, and generated snapshot slot/requirement payload.
- [x] Run `python -m pytest tests\api\test_schedule_runs_api.py -q` and confirm the new tests fail for the expected missing behavior.

### Task 2: ScheduleRun Immutability And Scoped Override

**Files:**
- Modify: `src/work_schedule_ai/api/routes/schedule_runs.py`

- [x] Reject recalculation when `_get_publication_for_run(run, db_session)` returns a published publication.
- [x] Generate `approve_time_off_override` proposals only when an overrideable unavailable employee can satisfy the issue's role and slot.
- [x] Encode proposal ids with employee and slot identity, and apply approval only to that employee/slot pair.
- [x] Use `mark_manual_review` proposal when no scoped time-off override candidate exists.

### Task 3: Manual Edit Validation API

**Files:**
- Modify: `src/work_schedule_ai/api/routes/schedule_runs.py`

- [x] Add request/response models matching `ManualEditValidationRequest` and `ManualEditValidationResponse`.
- [x] Add `POST /{organization_id}/schedule-runs/{schedule_run_id}/manual-edits/validate`.
- [x] Validate publication lock, slot existence, role existence, employee active state, employee role eligibility, unavailability overlap, and blocked pair conflicts in the same slot.

### Task 4: Snapshot Reproducibility

**Files:**
- Modify: `src/work_schedule_ai/api/routes/schedule_runs.py`
- Modify: `tests/api/test_schedule_runs_api.py`

- [x] Add `generated_shift_slots` and `generated_schedule_requirements` to `ScheduleInputSnapshot.payload_json` for shift-template runs.
- [x] Keep sorted deterministic payload ordering.

### Task 5: PostgreSQL Tenant RLS

**Files:**
- Create: `alembic/versions/20260624_0009_m1_postgresql_rls.py`
- Modify: `src/work_schedule_ai/api/dependencies.py`
- Modify: `src/work_schedule_ai/api/routes/organizations.py`
- Modify: `tests/db/test_alembic_migrations.py`

- [x] Add PostgreSQL-only migration enabling and forcing RLS on tenant child tables with `organization_id = current_setting('app.current_organization_id', true)`.
- [x] Set `app.current_organization_id` from organization path params in `get_db_session`.
- [x] Set tenant context manually during organization creation before default role insert.
- [x] Add migration tests for revision head and RLS policy SQL.

### Task 6: Verification And Commit

- [x] Run focused API tests.
- [x] Run full pytest.
- [x] Run frontend build.
- [x] Run `git diff --check`.
- [x] Update task docs and commit only this remediation's files, leaving pre-existing review doc changes unstaged.
