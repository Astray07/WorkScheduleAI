# First Release Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans and superpowers:test-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close WorkScheduleAI's first-release completion gates with CI, PostgreSQL RLS verification, persisted solver diagnostics, and a release checklist.

**Architecture:** Add a `solver_diagnostic_events` table alongside persisted schedule artifacts. Store diagnostic rows whenever schedule artifacts are replaced. Add PostgreSQL-only integration tests that run alembic against a temporary database and verify RLS as a non-superuser app role. Add GitHub Actions to run backend, PostgreSQL RLS, and frontend gates.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, PostgreSQL/psycopg, GitHub Actions, Vite.

---

### Task 1: Diagnostic Event Regression Tests

**Files:**
- Modify: `tests/api/test_schedule_runs_api.py`
- Modify: `tests/db/test_domain_models.py`
- Modify: `tests/db/test_alembic_migrations.py`

- [x] Add tests asserting solver issue generation persists `SolverDiagnosticEvent` rows.
- [x] Add domain/migration tests for the new table and indexes.
- [x] Run focused tests and confirm failures before implementation.

### Task 2: Diagnostic Event Persistence

**Files:**
- Modify: `src/work_schedule_ai/db/models.py`
- Create: `alembic/versions/20260624_0010_m1_solver_diagnostic_events.py`
- Modify: `src/work_schedule_ai/api/routes/schedule_runs.py`

- [x] Add `SolverDiagnosticEvent` model and migration.
- [x] Delete/reinsert diagnostic rows together with persisted artifacts.
- [x] Generate `infeasibility_core` rows for ScheduleIssue and `unary_exclusion` or `manual_review` rows for proposals.
- [x] Include the table in PostgreSQL RLS policy setup for the new migration.

### Task 3: PostgreSQL RLS Integration Test

**Files:**
- Create: `tests/db/test_postgresql_rls_integration.py`
- Modify: `pyproject.toml`

- [x] Add psycopg to dev dependencies or ensure CI installs deploy dependencies.
- [x] Add a test that skips unless `TEST_POSTGRES_URL` is set.
- [x] In the test, create a temporary database, run alembic head, create a non-superuser app role, grant table access, and verify tenant RLS select/insert behavior.

### Task 4: CI Workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [x] Add backend job installing `.[dev,deploy]`, running `python -m pytest -q`, and running PostgreSQL RLS integration with a postgres service.
- [x] Add frontend job running `npm ci` and `npm run build` in `frontend`.

### Task 5: Release Checklist

**Files:**
- Create: `docs/release/first-release-checklist.md`
- Modify: `work/tasks/2026-06-24-first-release-completion/*.md`

- [x] Document completed first-release capabilities and explicit follow-up hardening items.
- [x] Record verification commands and outcomes.

### Task 6: Verification And Commit

- [x] Run focused tests.
- [x] Run full pytest.
- [x] Run frontend build.
- [x] Run `git diff --check`.
- [x] Commit only first-release completion files, leaving pre-existing review document changes unstaged.
