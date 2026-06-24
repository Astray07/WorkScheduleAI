# M1 Shift Template API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ShiftType and ShiftRequirement persistence plus minimal API endpoints for 1차 근무 유형/필요 인원 setup.

**Architecture:** Store shift templates as tenant-scoped master data. A ShiftType owns one or more ShiftRequirement rows by role; the API creates them together so the frontend can configure the basic `사수 1명 + 부사수 1명` template in one request.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy 2, Alembic, pytest.

---

### Task 1: Failing Tests

**Files:**
- Modify: `tests/db/test_domain_models.py`
- Modify: `tests/db/test_alembic_migrations.py`
- Add: `tests/api/test_shift_templates_api.py`

- [x] **Step 1: Add DB invariant tests**

Add tests requiring:
- `ShiftType` exists,
- `ShiftRequirement` exists,
- `shift_types(organization_id, name)` is unique,
- `ShiftRequirement.required_count >= 1`.

- [x] **Step 2: Add API tests**

Add tests for:
- creating a shift type with `사수 1명`, `부사수 1명`,
- listing shift types,
- rejecting an unknown role,
- rejecting duplicate shift type names.

- [x] **Step 3: Run RED verification**

Run:

```powershell
python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py tests/api/test_shift_templates_api.py -q
```

Expected: fail because models, migration, route, and app wiring do not exist.

### Task 2: Model and Migration

**Files:**
- Modify: `src/work_schedule_ai/db/models.py`
- Modify: `src/work_schedule_ai/db/__init__.py`
- Add: `alembic/versions/20260624_0007_m1_shift_templates.py`
- Modify: `tests/db/test_alembic_migrations.py`

- [x] **Step 1: Add SQLAlchemy models**

Add `ShiftType` with tenant scoped name, local start/end time, timezone, active, and `crosses_midnight`.

Add `ShiftRequirement` with tenant scoped `shift_type_id`, `role_id`, `required_count`, and optional `unfilled_weight_override`.

- [x] **Step 2: Add Alembic migration**

Create `shift_types` and `shift_requirements`, indexes, unique constraints, foreign keys, and positive count checks.

- [x] **Step 3: Run DB tests**

Run:

```powershell
python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py -q
```

Expected: pass.

### Task 3: API Route

**Files:**
- Add: `src/work_schedule_ai/api/routes/shift_templates.py`
- Modify: `src/work_schedule_ai/api/app.py`

- [x] **Step 1: Implement create endpoint**

`POST /organizations/{organization_id}/shift-types` validates organization and role ownership, rejects duplicate names, creates the shift type and requirements atomically, and returns requirement role names.

- [x] **Step 2: Implement list endpoint**

`GET /organizations/{organization_id}/shift-types` returns active and inactive shift types ordered by name with requirements ordered by role name.

- [x] **Step 3: Run API tests**

Run:

```powershell
python -m pytest tests/api/test_shift_templates_api.py -q
```

Expected: pass.

### Task 4: Verification and Commit

**Files:**
- Modify: `work/tasks/2026-06-24-m1-shift-template-api/verification.md`
- Modify: `work/tasks/2026-06-24-m1-shift-template-api/handoff.md`

- [x] **Step 1: Run full verification**

Run:

```powershell
python -m pytest -q
git diff --check
```

Expected: all tests pass and whitespace check exits 0.

- [x] **Step 2: Commit**

Run:

```powershell
git add docs/superpowers/plans/2026-06-24-m1-shift-template-api.md work/tasks/2026-06-24-m1-shift-template-api src tests alembic
git commit -m "feat: add shift template api"
```
