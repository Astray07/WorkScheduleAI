# M2 ScheduleRun Solver API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the OR-Tools solver foundation into ScheduleRun result generation when an organization has shift templates.

**Architecture:** Keep the existing no-template mock path for current P0 contract tests. Add a solver-backed path that translates ShiftType/ShiftRequirement, EmployeeRole, Unavailability, and blocked PairConstraint rows into solver DTOs, then maps solver output back to the existing result response shape.

**Tech Stack:** FastAPI route helpers, SQLAlchemy queries, OR-Tools solver module, pytest.

---

### Task 1: Failing API Tests

**Files:**
- Modify: `tests/api/test_schedule_runs_api.py`

- [x] **Step 1: Add solver-backed success test**

Seed a shift type requiring `사수` and `부사수`, create employees with role links, create a ScheduleRun, and assert result requirements/assignments come from the shift template.

- [x] **Step 2: Add solver-backed unfilled issue test**

Seed a shift type requiring a role no active employee can work, create a ScheduleRun, and assert the result contains an `unfilled_requirement` issue.

- [x] **Step 3: Run RED verification**

Run:

```powershell
python -m pytest tests/api/test_schedule_runs_api.py -q
```

Expected: fail because ScheduleRun still uses the legacy mock artifact builder even when shift templates exist.

### Task 2: API Solver Wiring

**Files:**
- Modify: `src/work_schedule_ai/api/routes/schedule_runs.py`

- [x] **Step 1: Import shift template and solver models**

Import `ShiftType`, `ShiftRequirement`, `EmployeeRole`, `PairConstraint`, `Unavailability`, solver DTOs, and `solve_schedule`.

- [x] **Step 2: Add solver-backed artifact builder**

If shift types exist for the organization, generate slots and requirements for each date in the run, translate employees and constraints into solver input, call `solve_schedule`, and map assignments/issues to the existing response DTOs.

- [x] **Step 3: Preserve existing mock path**

If no shift types exist, keep current mock result behavior unchanged so existing contract tests continue to pass.

- [x] **Step 4: Run focused API tests**

Run:

```powershell
python -m pytest tests/api/test_schedule_runs_api.py tests/api/test_p0_vertical_slice_api.py -q
```

Expected: pass.

### Task 3: Verification and Commit

**Files:**
- Modify: `work/tasks/2026-06-24-m2-schedule-run-solver-api/verification.md`
- Modify: `work/tasks/2026-06-24-m2-schedule-run-solver-api/handoff.md`

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
git add src/work_schedule_ai/api/routes/schedule_runs.py tests/api/test_schedule_runs_api.py docs/superpowers/plans/2026-06-24-m2-schedule-run-solver-api.md work/tasks/2026-06-24-m2-schedule-run-solver-api
git commit -m "feat: wire schedule runs to ortools solver"
```
