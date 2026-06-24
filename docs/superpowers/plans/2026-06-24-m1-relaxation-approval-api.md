# M1 Relaxation Approval API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `POST /organizations/{organization_id}/schedule-runs/{schedule_run_id}/relaxation-proposals/{proposal_id}/approve` for the P0 approval step.

**Architecture:** Add a persisted `OverrideApproval` table and extend the schedule run router. The API validates that the run exists, the proposal appears in the current mock result, and no approval already exists for the same run/proposal, then records the approval without incrementing `recalculation_count`.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, pytest, SQLite in-memory tests.

---

## File Structure

- Modify: `src/work_schedule_ai/db/models.py` - add `OverrideApproval`.
- Modify: `src/work_schedule_ai/db/__init__.py` - export `OverrideApproval`.
- Create: `alembic/versions/20260624_0004_m1_override_approvals.py` - create override approvals table.
- Modify: `tests/db/test_domain_models.py` - add duplicate approval constraint coverage.
- Modify: `tests/db/test_alembic_migrations.py` - expect override approvals table, constraint, index, and head revision.
- Modify: `tests/api/test_schedule_runs_api.py` - add approval API tests.
- Modify: `src/work_schedule_ai/api/routes/schedule_runs.py` - add approval schemas/endpoint and mark approved mock proposal status.
- Create: `work/tasks/2026-06-24-m1-relaxation-approval-api/*.md` - task harness notes.

## Task 1: Write Failing DB And API Tests

**Files:**
- Modify: `tests/db/test_domain_models.py`
- Modify: `tests/db/test_alembic_migrations.py`
- Modify: `tests/api/test_schedule_runs_api.py`

- [x] **Step 1: Add domain model test**

Test case:

- duplicate `(organization_id, schedule_run_id, relaxation_proposal_id)` override approval is rejected.

- [x] **Step 2: Add Alembic test coverage**

Assertions:

- `override_approvals` exists after `upgrade head`.
- named unique constraint `uq_override_approvals_run_proposal` exists.
- indexes include `ix_override_approvals_organization_id` and `ix_override_approvals_schedule_run_id`.
- `alembic_version` is `20260624_0004`.

- [x] **Step 3: Add API tests**

Test cases:

- approving `proposal_mock_time_off_1` returns 201, persists one approval, and leaves `recalculation_count=0`.
- result after approval marks the proposal status as `approved`.
- approving the same proposal twice returns 409 and keeps one approval.
- unknown proposal returns 404 and writes nothing.

- [x] **Step 4: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py tests/api/test_schedule_runs_api.py -q
```

Expected: FAIL because `OverrideApproval` and the approval endpoint are not implemented yet.

## Task 2: Implement Model And Migration

**Files:**
- Modify: `src/work_schedule_ai/db/models.py`
- Modify: `src/work_schedule_ai/db/__init__.py`
- Create: `alembic/versions/20260624_0004_m1_override_approvals.py`

- [x] **Step 1: Add `OverrideApproval` model**

Fields: `id`, `organization_id`, `schedule_run_id`, `relaxation_proposal_id`, `type`, `notification_required`, `reason`, `created_at`.

Constraints:

- `type` must be one of the M0 relaxation proposal types.
- `(organization_id, schedule_run_id, relaxation_proposal_id)` is unique.

- [x] **Step 2: Add Alembic revision**

Create the table with named constraints and indexes.

- [x] **Step 3: Run DB tests**

Run:

```powershell
python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py -q
```

Expected: DB model and migration tests pass.

## Task 3: Implement Approval API

**Files:**
- Modify: `src/work_schedule_ai/api/routes/schedule_runs.py`

- [x] **Step 1: Add request/response schemas**

Use `reason: str` with min length 1 and max length 500, plus `notification_required: bool`.

- [x] **Step 2: Validate run and proposal**

Rules:

- schedule run must exist in the organization, otherwise 404.
- proposal must exist in the current result payload, otherwise 404.
- duplicate approval returns 409.

- [x] **Step 3: Persist approval without recalculation**

Create `override_<uuid>`, commit once, return 201, and do not change `ScheduleRun.recalculation_count`.

- [x] **Step 4: Reflect approved status in result**

If an approval exists for a proposal, `GET /result` returns that proposal with `status=approved`.

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

Record RED/GREEN/full test results in `work/tasks/2026-06-24-m1-relaxation-approval-api/verification.md` and update handoff state.

- [x] **Step 4: Commit changes**

Run:

```powershell
git add src tests alembic docs/superpowers/plans/2026-06-24-m1-relaxation-approval-api.md work/tasks/2026-06-24-m1-relaxation-approval-api
git commit -m "feat: add relaxation approval api"
```
