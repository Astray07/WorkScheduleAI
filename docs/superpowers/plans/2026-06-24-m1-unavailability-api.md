# M1 Unavailability API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `POST /organizations/{organization_id}/unavailabilities` so P0 can register one vacation/business trip/training/personal unavailability.

**Architecture:** Add an `Unavailability` SQLAlchemy model and a second Alembic revision, then expose one focused FastAPI route. The route validates `ends_at > starts_at` and checks that the referenced employee belongs to the organization before inserting.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, pytest, SQLite in-memory tests.

---

## File Structure

- Modify: `src/work_schedule_ai/db/models.py` - add `Unavailability`.
- Create: `alembic/versions/20260624_0002_m1_unavailabilities.py` - create unavailability table and indexes.
- Modify: `tests/db/test_domain_models.py` - add time-order/type constraint coverage.
- Modify: `tests/db/test_alembic_migrations.py` - expect unavailability table, constraints, indexes, and new head revision.
- Create: `tests/api/test_unavailabilities_api.py` - TDD API tests for creation and validation.
- Create: `src/work_schedule_ai/api/routes/unavailabilities.py` - unavailability route and schemas.
- Modify: `src/work_schedule_ai/api/app.py` - include the unavailability router.
- Create: `work/tasks/2026-06-24-m1-unavailability-api/*.md` - task harness notes.

## Task 1: Write Failing DB And API Tests

**Files:**
- Modify: `tests/db/test_domain_models.py`
- Modify: `tests/db/test_alembic_migrations.py`
- Create: `tests/api/test_unavailabilities_api.py`

- [x] **Step 1: Add domain model tests**

Test cases:

- invalid `type` is rejected by `ck_unavailabilities_type`.
- `ends_at <= starts_at` is rejected by `ck_unavailabilities_time_order`.

- [x] **Step 2: Add Alembic tests**

Assertions:

- `unavailabilities` exists after `upgrade head`.
- named constraints include `ck_unavailabilities_type` and `ck_unavailabilities_time_order`.
- indexes include `ix_unavailabilities_organization_id`, `ix_unavailabilities_employee_id`, and `ix_unavailabilities_employee_time`.
- `alembic_version` is `20260624_0002`.

- [x] **Step 3: Add API tests**

Test cases:

- valid request creates one unavailability and returns 201.
- `ends_at` equal to `starts_at` returns 422 and writes nothing.
- employee from another organization returns 422 and writes nothing.

- [x] **Step 4: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py tests/api/test_unavailabilities_api.py -q
```

Expected: FAIL because `Unavailability` and the route are not implemented yet.

## Task 2: Implement Model And Migration

**Files:**
- Modify: `src/work_schedule_ai/db/models.py`
- Create: `alembic/versions/20260624_0002_m1_unavailabilities.py`

- [x] **Step 1: Add `Unavailability` model**

Fields: `id`, `organization_id`, `employee_id`, `type`, `starts_at`, `ends_at`, `override_allowed`, `note`, `created_at`.

Constraints:

- `ck_unavailabilities_type`: `type IN ('vacation', 'business_trip', 'training', 'personal')`
- `ck_unavailabilities_time_order`: `starts_at < ends_at`

- [x] **Step 2: Add Alembic revision**

Create the table with named constraints and indexes:

- `ix_unavailabilities_organization_id`
- `ix_unavailabilities_employee_id`
- `ix_unavailabilities_employee_time`

- [x] **Step 3: Run DB tests**

Run:

```powershell
python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py -q
```

Expected: DB model and migration tests pass.

## Task 3: Implement API Route

**Files:**
- Create: `src/work_schedule_ai/api/routes/unavailabilities.py`
- Modify: `src/work_schedule_ai/api/app.py`

- [x] **Step 1: Add request/response schemas**

Use `Literal["vacation", "business_trip", "training", "personal"]` for `type`, `datetime` for `starts_at`/`ends_at`, and `note` max length 500.

- [x] **Step 2: Validate request**

Rules:

- `ends_at` must be after `starts_at`.
- organization must exist, otherwise 404.
- employee must exist in the same organization, otherwise 422.

- [x] **Step 3: Insert and return response**

Create `unavailability_<uuid>` IDs, commit once, and return the M0 response fields with status 201.

- [x] **Step 4: Run API tests**

Run:

```powershell
python -m pytest tests/api/test_unavailabilities_api.py -q
```

Expected: all unavailability API tests pass.

## Task 4: Verify, Document, And Commit

- [x] **Step 1: Run focused and full tests**

Run:

```powershell
python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py tests/api/test_unavailabilities_api.py -q
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

Record RED/GREEN/full test results in `work/tasks/2026-06-24-m1-unavailability-api/verification.md` and update handoff state.

- [x] **Step 4: Commit changes**

Run:

```powershell
git add src tests alembic docs/superpowers/plans/2026-06-24-m1-unavailability-api.md work/tasks/2026-06-24-m1-unavailability-api
git commit -m "feat: add unavailability creation api"
```
