# M1 Domain Tenancy DB Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first tenant-aware SQLAlchemy domain models and constraint tests.

**Architecture:** This step defines the M1 foundation tables for organization, user, membership, employee, role, employee role, and pair constraint. It tests core uniqueness and normalization behavior with SQLite in-memory while preserving PostgreSQL-oriented naming and constraint intent for later Alembic migration work.

**Tech Stack:** Python 3.13, SQLAlchemy 2.0, pytest, SQLite in-memory test engine.

---

## File Structure

- Modify: `pyproject.toml` - add SQLAlchemy runtime dependency and Alembic dev dependency.
- Create: `src/work_schedule_ai/db/__init__.py` - DB package exports.
- Create: `src/work_schedule_ai/db/models.py` - SQLAlchemy declarative models and pair normalization helper.
- Create: `tests/db/test_domain_models.py` - TDD DB model constraint tests.
- Create: `work/tasks/2026-06-24-m1-domain-tenancy-db-foundation/*.md` - task harness.

## Task 1: Write DB Model Tests First

**Files:**
- Create: `tests/db/test_domain_models.py`

- [x] **Step 1: Write failing tests**

Write tests that import `Base`, `Employee`, `EmployeeRole`, `Membership`, `Organization`, `PairConstraint`, `Role`, `User`, and `normalize_pair_employee_ids` from `work_schedule_ai.db.models`.

Required behaviors:

- employee code is unique inside an organization but can repeat across organizations.
- role name is unique inside an organization but can repeat across organizations.
- employee role assignments cannot be duplicated.
- pair constraints normalize employee order.
- inverse pair constraint duplicates are rejected.
- self pair constraints are rejected before DB insert.
- membership is unique per organization/user.

- [x] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/db/test_domain_models.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'work_schedule_ai.db'`.

## Task 2: Implement Minimal SQLAlchemy Models

**Files:**
- Modify: `pyproject.toml`
- Create: `src/work_schedule_ai/db/__init__.py`
- Create: `src/work_schedule_ai/db/models.py`

- [x] **Step 1: Add dependencies**

Add `SQLAlchemy>=2.0,<3` to runtime dependencies and `alembic>=1.16,<2` to dev dependencies.

- [x] **Step 2: Implement declarative base and models**

Use `DeclarativeBase`, `Mapped`, and `mapped_column`. Use string ids, `DateTime(timezone=True)`, `Text`, `Boolean`, `Integer`, `ForeignKey`, `UniqueConstraint`, and `CheckConstraint`.

- [x] **Step 3: Implement pair normalization helper**

`normalize_pair_employee_ids(employee_a_id, employee_b_id)` returns sorted ids and raises `ValueError` when the ids are equal.

- [x] **Step 4: Run DB tests and verify GREEN**

Run:

```powershell
python -m pytest tests/db/test_domain_models.py -q
```

Expected: all DB tests pass.

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

Expected: no output and exit 0.

- [x] **Step 3: Update verification and handoff**

Record RED/GREEN/full test results and remaining risks.

- [x] **Step 4: Commit changes**

Run:

```powershell
git add pyproject.toml src tests docs/superpowers/plans/2026-06-24-m1-domain-tenancy-db-foundation.md work/tasks/2026-06-24-m1-domain-tenancy-db-foundation
git commit -m "feat: add tenant domain db models"
```
