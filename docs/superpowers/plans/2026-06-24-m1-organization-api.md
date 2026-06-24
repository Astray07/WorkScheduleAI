# M1 Organization API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `POST /organizations` with DB persistence and default role creation.

**Architecture:** Add a sync SQLAlchemy session dependency, a small organization route module, and Pydantic request/response schemas. Tests override the DB session with an in-memory SQLite database and verify both response shape and persisted rows.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2.0, pytest, SQLite in-memory tests.

---

## File Structure

- Create: `src/work_schedule_ai/api/dependencies.py` - sync DB session dependency.
- Create: `src/work_schedule_ai/api/routes/__init__.py` - route package marker.
- Create: `src/work_schedule_ai/api/routes/organizations.py` - organization router and schemas.
- Modify: `src/work_schedule_ai/api/app.py` - include organization router.
- Create: `tests/api/test_organizations_api.py` - TDD API tests.
- Create: `work/tasks/2026-06-24-m1-organization-api/*.md` - task harness.

## Task 1: Write Organization API Tests First

**Files:**
- Create: `tests/api/test_organizations_api.py`

- [x] **Step 1: Write failing tests**

Tests should verify:

- `POST /organizations` returns 201 and default roles.
- DB contains one organization and two roles after request.
- empty name returns 422.

- [x] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/api/test_organizations_api.py -q
```

Expected: FAIL because `/organizations` is not implemented.

## Task 2: Implement Organization Route

**Files:**
- Create: `src/work_schedule_ai/api/dependencies.py`
- Create: `src/work_schedule_ai/api/routes/__init__.py`
- Create: `src/work_schedule_ai/api/routes/organizations.py`
- Modify: `src/work_schedule_ai/api/app.py`

- [x] **Step 1: Add DB session dependency**

Add a default `get_db_session()` generator. Tests will override it.

- [x] **Step 2: Add Pydantic schemas**

Add `OrganizationCreateRequest`, `RoleResponse`, and `OrganizationResponse`.

- [x] **Step 3: Add route**

Persist organization and default roles, commit, refresh, and return response.

- [x] **Step 4: Include router in app**

`create_app()` should include the organization router.

- [x] **Step 5: Run tests and verify GREEN**

Run:

```powershell
python -m pytest tests/api/test_organizations_api.py -q
```

Expected: all organization API tests pass.

## Task 3: Verify And Commit

- [x] **Step 1: Run full tests**

Run:

```powershell
python -m pytest -q
```

Expected: all tests pass.

- [x] **Step 2: Run diff check**

Run:

```powershell
git diff --check
```

Expected: no whitespace errors.

- [x] **Step 3: Update verification and handoff**

Record RED/GREEN/full test results.

- [x] **Step 4: Commit changes**

Run:

```powershell
git add src tests docs/superpowers/plans/2026-06-24-m1-organization-api.md work/tasks/2026-06-24-m1-organization-api
git commit -m "feat: add organization creation api"
```
