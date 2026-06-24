# M1 Employee Bulk Paste API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `POST /organizations/{organization_id}/employees/bulk-paste` so P0 can register four employees from pasted rows.

**Architecture:** Add one focused FastAPI router for employee bulk paste. Reuse the existing SQLAlchemy `Organization`, `Employee`, `Role`, and `EmployeeRole` models, validate request-local duplicate employee codes and role names before writing, and keep `validate_only` side-effect free.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2.0, pytest, SQLite in-memory tests.

---

## File Structure

- Create: `tests/api/test_employee_bulk_paste_api.py` - TDD coverage for validate-only, upsert, duplicate employee codes, unknown roles, and existing employee updates.
- Create: `src/work_schedule_ai/api/routes/employees.py` - employee bulk paste router and local Pydantic schemas.
- Modify: `src/work_schedule_ai/api/app.py` - include the employee router.
- Create: `work/tasks/2026-06-24-m1-employee-bulk-paste-api/*.md` - task harness notes.

## Task 1: Write Employee Bulk Paste Tests First

**Files:**
- Create: `tests/api/test_employee_bulk_paste_api.py`

- [x] **Step 1: Write failing tests**

Add tests with an in-memory SQLite DB, seeded organization `org_1`, roles `role_senior`/`role_junior`, and dependency override for `get_db_session`.

Test cases:

- `mode=validate_only` returns `valid=true`, zero created/updated counts, no errors, and persists no employees.
- `mode=upsert` creates employees and employee-role rows.
- duplicate `employee_code` in the same payload returns `valid=false` with `DUPLICATE_EMPLOYEE_CODE` and no writes.
- unknown role returns `valid=false` with `UNKNOWN_ROLE` and no writes.
- upsert of an existing employee updates name and role links, counted as one update.

- [x] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/api/test_employee_bulk_paste_api.py -q
```

Expected: FAIL because the route is not implemented yet.

## Task 2: Implement Minimal Employee Router

**Files:**
- Create: `src/work_schedule_ai/api/routes/employees.py`
- Modify: `src/work_schedule_ai/api/app.py`

- [x] **Step 1: Add local request/response schemas**

Schemas:

- `EmployeeBulkPasteRow`
- `EmployeeBulkPasteRequest`
- `FieldError`
- `EmployeeResponse`
- `EmployeeBulkPasteResponse`

- [x] **Step 2: Add validation before writes**

Validation rules:

- Organization must exist, otherwise return 404.
- Duplicate `employee_code` in one request creates a row error with field `employee_code`.
- Unknown `role_names` create row errors with field `role_names`.
- If any row error exists, return `valid=false` with zero counts and do not write.

- [x] **Step 3: Implement `validate_only`**

For valid input with `mode=validate_only`, return `valid=true`, zero counts, no errors, and an empty `employees` list.

- [x] **Step 4: Implement `upsert`**

For `mode=upsert`, create missing employees, update existing employees by `(organization_id, employee_code)`, replace their role links with the provided roles, commit once, and return imported employees with role IDs.

- [x] **Step 5: Include router in app**

`create_app()` should include the employee router after the organization router.

- [x] **Step 6: Run tests and verify GREEN**

Run:

```powershell
python -m pytest tests/api/test_employee_bulk_paste_api.py -q
```

Expected: all employee bulk paste API tests pass.

## Task 3: Verify, Document, And Commit

- [x] **Step 1: Run focused and full tests**

Run:

```powershell
python -m pytest tests/api/test_employee_bulk_paste_api.py -q
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

Record RED/GREEN/full test results in `work/tasks/2026-06-24-m1-employee-bulk-paste-api/verification.md` and update handoff state.

- [x] **Step 4: Commit changes**

Run:

```powershell
git add src tests docs/superpowers/plans/2026-06-24-m1-employee-bulk-paste-api.md work/tasks/2026-06-24-m1-employee-bulk-paste-api
git commit -m "feat: add employee bulk paste api"
```
