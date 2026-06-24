# M1 Pair Constraint API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `POST /organizations/{organization_id}/pair-constraints` so P0 can register one blocked/avoid/prefer employee pair constraint.

**Architecture:** Reuse the existing `PairConstraint` SQLAlchemy model and normalization helper. Add one focused FastAPI router that validates organization membership, rejects self-pairs, detects normalized duplicates before insert, and returns the normalized IDs required by the M0 contract.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2.0, pytest, SQLite in-memory tests.

---

## File Structure

- Create: `tests/api/test_pair_constraints_api.py` - TDD API tests for creation, self-pair rejection, cross-organization rejection, and inverse duplicate conflict.
- Create: `src/work_schedule_ai/api/routes/pair_constraints.py` - pair constraint route and schemas.
- Modify: `src/work_schedule_ai/api/app.py` - include the pair constraint router.
- Create: `work/tasks/2026-06-24-m1-pair-constraint-api/*.md` - task harness notes.

## Task 1: Write Pair Constraint API Tests First

**Files:**
- Create: `tests/api/test_pair_constraints_api.py`

- [x] **Step 1: Write failing tests**

Test cases:

- valid request creates a pair constraint, normalizes employee order, and returns 201.
- same employee in both fields returns 422 and writes nothing.
- employee from another organization returns 422 and writes nothing.
- inverse duplicate for the same `type` returns 409 and keeps one row.

- [x] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/api/test_pair_constraints_api.py -q
```

Expected: FAIL because `/organizations/{organization_id}/pair-constraints` is not implemented yet.

## Task 2: Implement Minimal Pair Constraint Router

**Files:**
- Create: `src/work_schedule_ai/api/routes/pair_constraints.py`
- Modify: `src/work_schedule_ai/api/app.py`

- [x] **Step 1: Add request/response schemas**

Use `Literal["blocked", "avoid", "prefer"]` for `type`, `Literal["low", "medium", "high", "critical"]` for `severity`, default `severity` to `high`, and default `active` to `true`.

- [x] **Step 2: Validate request**

Rules:

- organization must exist, otherwise 404.
- `employee_a_id` and `employee_b_id` must differ, otherwise 422.
- both employees must belong to the organization, otherwise 422.
- normalized duplicate `(organization_id, normalized_employee_a_id, normalized_employee_b_id, type)` returns 409.

- [x] **Step 3: Insert and return response**

Create `pair_<uuid>` IDs through `PairConstraint.create(...)`, commit once, and return request fields plus `normalized_employee_a_id`/`normalized_employee_b_id`.

- [x] **Step 4: Run tests and verify GREEN**

Run:

```powershell
python -m pytest tests/api/test_pair_constraints_api.py -q
```

Expected: all pair constraint API tests pass.

## Task 3: Verify, Document, And Commit

- [x] **Step 1: Run focused and full tests**

Run:

```powershell
python -m pytest tests/api/test_pair_constraints_api.py -q
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

Record RED/GREEN/full test results in `work/tasks/2026-06-24-m1-pair-constraint-api/verification.md` and update handoff state.

- [x] **Step 4: Commit changes**

Run:

```powershell
git add src tests docs/superpowers/plans/2026-06-24-m1-pair-constraint-api.md work/tasks/2026-06-24-m1-pair-constraint-api
git commit -m "feat: add pair constraint api"
```
