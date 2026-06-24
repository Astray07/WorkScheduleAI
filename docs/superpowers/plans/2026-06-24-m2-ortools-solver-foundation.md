# M2 OR-Tools Solver Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an isolated OR-Tools CP-SAT solver module for the 1차 scheduling core.

**Architecture:** Keep solver data classes independent from SQLAlchemy and FastAPI. The API will later translate ScheduleRun snapshots into solver input; this step only proves the solver handles role requirements, unavailability, blocked pairs, unfilled soft penalty, and deterministic ordering.

**Tech Stack:** Python dataclasses, OR-Tools CP-SAT, pytest.

---

### Task 1: Failing Solver Tests

**Files:**
- Add: `tests/solver/test_ortools_solver.py`

- [x] **Step 1: Add golden case test**

Test 4 employees, 7 slots, 2 roles, one required employee per role per slot, and assert 14 assignments with no issues.

- [x] **Step 2: Add hard constraint and soft issue tests**

Test role eligibility, employee unavailability, blocked pair exclusion, and a case where a required role cannot be filled and becomes an `unfilled_requirement` issue instead of failing the solve.

- [x] **Step 3: Add deterministic repeat test**

Run the same input twice and assert assignment tuples are identical.

- [x] **Step 4: Run RED verification**

Run:

```powershell
python -m pytest tests/solver/test_ortools_solver.py -q
```

Expected: fail because the solver package does not exist yet.

### Task 2: Dependency and Solver Implementation

**Files:**
- Modify: `pyproject.toml`
- Add: `src/work_schedule_ai/solver/__init__.py`
- Add: `src/work_schedule_ai/solver/models.py`
- Add: `src/work_schedule_ai/solver/ortools_solver.py`

- [x] **Step 1: Add OR-Tools dependency**

Add `ortools>=9.14,<10` to project dependencies and install editable dev dependencies locally.

- [x] **Step 2: Add solver DTOs**

Add immutable input DTOs for employees, slots, requirements, blocked pairs, and solve request; add output DTOs for assignments, issues, and status.

- [x] **Step 3: Implement CP-SAT model**

Create assignment booleans only for eligible employees. Add:
- requirement capacity with unfilled soft variable,
- one role per employee per slot,
- unavailable employee hard exclusion,
- blocked pair hard exclusion,
- objective minimizing unfilled weighted penalty.

- [x] **Step 4: Run focused tests**

Run:

```powershell
python -m pytest tests/solver/test_ortools_solver.py -q
```

Expected: pass.

### Task 3: Verification and Commit

**Files:**
- Modify: `work/tasks/2026-06-24-m2-ortools-solver-foundation/verification.md`
- Modify: `work/tasks/2026-06-24-m2-ortools-solver-foundation/handoff.md`

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
git add pyproject.toml src/work_schedule_ai/solver tests/solver docs/superpowers/plans/2026-06-24-m2-ortools-solver-foundation.md work/tasks/2026-06-24-m2-ortools-solver-foundation
git commit -m "feat: add ortools solver foundation"
```
