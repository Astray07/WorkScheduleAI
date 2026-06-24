# M6 Railway Release Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for seed behavior and superpowers:executing-plans task-by-task.

**Goal:** Add deployable Railway assets and an idempotent P0 demo seed for the 1차 릴리즈 candidate.

**Architecture:** Use a root Dockerfile and `railway.json` for the API service. Keep frontend as a separate Railway service rooted at `frontend/`. Run Alembic through `DATABASE_URL`. Seed data directly with SQLAlchemy stable IDs.

**Reference Check Date:** 2026-06-24.

---

### Task 1: Seed Tests

**Files:**
- Create: `tests/scripts/test_seed_demo.py`

- [x] **Step 1: Add idempotency test**

Run `seed_demo(session)` twice against an in-memory database and assert counts do not duplicate.

- [x] **Step 2: Add publication hash test**

Assert the seeded SchedulePublication hashes match the current generated artifacts.

### Task 2: Seed Implementation

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/seed_demo.py`

- [x] **Step 1: Implement stable id upserts**

Create demo organization, roles, 4 employees, employee-role links, vacation, pair constraint, approved override, recalculation record, ScheduleRun, ScheduleInputSnapshot, and SchedulePublication.

- [x] **Step 2: Add CLI entrypoint**

`python -m scripts.seed_demo` should use `DATABASE_URL` through the app dependency engine and print a JSON summary.

### Task 3: Railway Assets

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `railway.json`
- Create: `frontend/railway.json`
- Modify: `pyproject.toml`
- Modify: `alembic/env.py`
- Modify: `src/work_schedule_ai/api/app.py`
- Create: `docs/deployment/railway.md`

- [x] **Step 1: Add deploy dependencies and Dockerfile**

Add `deploy` optional dependency with Alembic and Uvicorn. Dockerfile installs `.[deploy]`.

- [x] **Step 2: Add Railway config**

Root service runs migration pre-deploy, starts FastAPI, and uses `/health` healthcheck. Frontend service builds Vite and previews static assets.

- [x] **Step 3: Add env-aware Alembic and CORS**

Read `DATABASE_URL` for migrations and `CORS_ALLOW_ORIGINS` for deployed frontend origins.

- [x] **Step 4: Document setup**

Document API, frontend, worker, PostgreSQL, Redis, env vars, migration, seed, and smoke checks.

### Task 4: Verification and Commit

- [x] **Step 1: Run focused checks**

```powershell
python -m pytest tests\scripts\test_seed_demo.py -q
python -m pytest tests\api\test_api_smoke.py -q
```

- [x] **Step 2: Run migration/seed smoke**

Use a temp SQLite `DATABASE_URL`, run Alembic, then `python -m scripts.seed_demo`.

- [x] **Step 3: Run full verification**

```powershell
python -m pytest -q
cd frontend
npm run build
git diff --check
```

- [x] **Step 4: Commit**

```powershell
git add Dockerfile .dockerignore railway.json frontend/railway.json pyproject.toml alembic/env.py src/work_schedule_ai/api/app.py scripts tests/scripts docs/deployment/railway.md docs/superpowers/plans/2026-06-24-m6-railway-release-assets.md work/tasks/2026-06-24-m6-railway-release-assets work/tasks/2026-06-24-first-release-execution
git commit -m "feat: add railway release assets"
```
