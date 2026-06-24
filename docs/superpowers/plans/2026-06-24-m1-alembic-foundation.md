# M1 Alembic Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Alembic scaffolding and an initial migration for the M1 tenant/domain foundation tables.

**Architecture:** Alembic uses `work_schedule_ai.db.models.Base.metadata` as target metadata. Tests run migrations against a temporary SQLite database to verify the migration path creates expected tables and named constraints without requiring a local PostgreSQL service.

**Tech Stack:** Python 3.13, SQLAlchemy 2.0, Alembic 1.16, pytest, SQLite temporary database.

---

## File Structure

- Create: `alembic.ini` - Alembic CLI configuration.
- Create: `alembic/env.py` - migration environment wired to SQLAlchemy metadata.
- Create: `alembic/script.py.mako` - revision template.
- Create: `alembic/versions/20260624_0001_m1_domain_tenancy.py` - initial M1 foundation migration.
- Create: `tests/db/test_alembic_migrations.py` - Alembic migration tests.
- Create: `work/tasks/2026-06-24-m1-alembic-foundation/*.md` - task harness.

## Task 1: Write Migration Tests First

**Files:**
- Create: `tests/db/test_alembic_migrations.py`

- [x] **Step 1: Write failing tests**

Tests should:

- Create a temporary SQLite database URL.
- Run `alembic.command.upgrade(config, "head")`.
- Inspect table names and assert the M1 foundation tables exist.
- Inspect unique/check constraints and assert expected constraint names exist.
- Assert the Alembic version table is stamped with `20260624_0001`.

- [x] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/db/test_alembic_migrations.py -q
```

Expected: FAIL because `alembic.ini` and migration scripts do not exist yet.

## Task 2: Implement Alembic Scaffolding

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/20260624_0001_m1_domain_tenancy.py`

- [x] **Step 1: Add Alembic config**

Set `script_location = alembic` and a placeholder SQLite URL. Tests will override `sqlalchemy.url`.

- [x] **Step 2: Add env.py**

Import `Base` from `work_schedule_ai.db.models`, set `target_metadata = Base.metadata`, and support online/offline migrations.

- [x] **Step 3: Add initial revision**

Create tables for organizations, users, memberships, employees, roles, employee_roles, and pair_constraints with named PK/FK/unique/check constraints.

- [x] **Step 4: Run migration tests and verify GREEN**

Run:

```powershell
python -m pytest tests/db/test_alembic_migrations.py -q
```

Expected: all migration tests pass.

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

Record RED/GREEN/full test results and remaining risks.

- [x] **Step 4: Commit changes**

Run:

```powershell
git add alembic alembic.ini tests/db/test_alembic_migrations.py docs/superpowers/plans/2026-06-24-m1-alembic-foundation.md work/tasks/2026-06-24-m1-alembic-foundation
git commit -m "feat: add alembic foundation migration"
```
