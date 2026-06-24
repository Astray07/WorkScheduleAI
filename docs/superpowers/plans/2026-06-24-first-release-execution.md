# First Release Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drive WorkScheduleAI from the current P0 backend slice to a 1차 릴리즈 candidate with backend contracts, solver path, frontend demo flow, privacy fallback tests, and deployment assets.

**Architecture:** Keep each milestone independently testable and committed. Backend remains FastAPI + SQLAlchemy/Alembic; solver work will be isolated behind a service module so OR-Tools can replace the current mock result without changing public API shape. Frontend will be a compact operational UI that calls the existing API and demonstrates the P0 flow.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, pytest, OR-Tools, React/Vite or the repo-selected frontend scaffold, browser tests, Railway deployment assets.

---

### Task 1: Shift Type and Requirement Foundation

**Files:**
- Create: `docs/superpowers/plans/2026-06-24-m1-shift-template-api.md`
- Create: `work/tasks/2026-06-24-m1-shift-template-api/brief.md`
- Create: `work/tasks/2026-06-24-m1-shift-template-api/plan.md`
- Create: `work/tasks/2026-06-24-m1-shift-template-api/decisions.md`
- Create: `work/tasks/2026-06-24-m1-shift-template-api/verification.md`
- Create: `work/tasks/2026-06-24-m1-shift-template-api/handoff.md`
- Modify: `src/work_schedule_ai/db/models.py`
- Modify: `src/work_schedule_ai/db/__init__.py`
- Create: `alembic/versions/20260624_0007_m1_shift_templates.py`
- Create: `src/work_schedule_ai/api/routes/shift_templates.py`
- Modify: `src/work_schedule_ai/api/app.py`
- Modify: `tests/db/test_domain_models.py`
- Modify: `tests/db/test_alembic_migrations.py`
- Create: `tests/api/test_shift_templates_api.py`

- [ ] **Step 1: Write failing tests for DB invariants and API**

Add tests that require `ShiftType` and `ShiftRequirement` to exist, enforce `shift_types(organization_id, name)` uniqueness, enforce positive `required_count`, create a default shift template for an organization, and reject unknown role IDs.

- [ ] **Step 2: Run RED verification**

Run:

```powershell
python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py tests/api/test_shift_templates_api.py -q
```

Expected: fail because shift template models, migration, and API do not exist yet.

- [ ] **Step 3: Implement model, migration, API, and route wiring**

Add `ShiftType` and `ShiftRequirement` with minimal 1차 fields: organization, name, local start/end time, timezone, active, role requirements, and optional unfilled weight override.

- [ ] **Step 4: Run focused and full verification**

Run:

```powershell
python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py tests/api/test_shift_templates_api.py -q
python -m pytest -q
git diff --check
```

Expected: all pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add docs/superpowers/plans/2026-06-24-m1-shift-template-api.md work/tasks/2026-06-24-m1-shift-template-api src tests alembic
git commit -m "feat: add shift template api"
```

### Task 2: OR-Tools Solver MVP

**Files:**
- Modify: `pyproject.toml`
- Create: `src/work_schedule_ai/solver/__init__.py`
- Create: `src/work_schedule_ai/solver/models.py`
- Create: `src/work_schedule_ai/solver/ortools_solver.py`
- Create: `tests/solver/test_ortools_solver.py`
- Modify: `src/work_schedule_ai/api/routes/schedule_runs.py`
- Modify: `tests/api/test_schedule_runs_api.py`

- [ ] **Step 1: Add solver tests**

Add golden tests for 4 employees, 7 days, 2 roles, vacation exclusion, blocked pair exclusion, and deterministic repeat output.

- [ ] **Step 2: Add OR-Tools dependency and verify import**

Run:

```powershell
python -m pip install -e .[dev]
python -c "import ortools; print(ortools.__version__)"
```

Expected: OR-Tools imports successfully. If Python 3.13 wheel support blocks install, document the blocker and implement the solver interface with a deterministic fallback until the runtime version is changed.

- [ ] **Step 3: Implement the minimal CP-SAT solver**

Use hard constraints for role eligibility, employee availability, blocked pairs, and one assignment per employee per slot. Model unfilled requirements as soft penalty variables that become ScheduleIssue rows.

- [ ] **Step 4: Wire ScheduleRun result through the solver service**

Preserve existing response shape and P0 tests while replacing hard-coded mock assignment generation for supported 1차 templates.

- [ ] **Step 5: Verify and commit**

Run:

```powershell
python -m pytest tests/solver tests/api/test_schedule_runs_api.py tests/api/test_p0_vertical_slice_api.py -q
python -m pytest -q
git diff --check
git commit -m "feat: add ortools solver mvp"
```

### Task 3: ScheduleRun Worker Semantics

**Files:**
- Modify: `src/work_schedule_ai/api/routes/schedule_runs.py`
- Create: `src/work_schedule_ai/worker/schedule_worker.py`
- Create: `tests/worker/test_schedule_worker.py`
- Modify: `tests/api/test_schedule_runs_api.py`

- [ ] **Step 1: Add tests for queued/running/succeeded/canceled and retry cleanup**

Tests must confirm idempotency, status transitions, `current_attempt_no` versus `recalculation_count`, cancel behavior, and retry cleanup.

- [ ] **Step 2: Implement synchronous in-process worker adapter for 1차**

Expose worker-compatible functions without requiring Redis in local tests. Keep Railway worker start command possible.

- [ ] **Step 3: Verify and commit**

Run full tests and commit.

### Task 4: Frontend P0 Operational UI

**Files:**
- Create frontend scaffold under the repo-selected frontend directory.
- Add organization setup, bulk employee entry, unavailability/pair forms, schedule result grid, issue/proposal panel, approval/recalculate/publish/download controls.
- Add browser verification tests.

- [ ] **Step 1: Use the relevant frontend skill and inspect available tooling**

Use the repo's actual frontend stack if one exists. If none exists, choose a minimal Vite React app and document the choice.

- [ ] **Step 2: Build the P0 flow as the first screen**

Do not build a landing page. Show an operational workflow immediately.

- [ ] **Step 3: Verify in browser and commit**

Run frontend tests, backend tests, and screenshot-based checks.

### Task 5: LLM Explanation Safety Layer

**Files:**
- Create: `src/work_schedule_ai/llm/explanations.py`
- Create: `tests/llm/test_explanations.py`
- Modify result/proposal response construction as needed.

- [ ] **Step 1: Add anonymization and fallback tests**

Verify payload contains no employee names, organization names, emails, or raw numeric loss scores.

- [ ] **Step 2: Implement template-first explanation service**

Keep external LLM optional. Fallback must be the default in tests and local dev.

- [ ] **Step 3: Verify and commit**

Run full tests and commit.

### Task 6: Railway Release Assets and Demo Data

**Files:**
- Create: `Dockerfile`
- Create: `railway.json`
- Create: `Procfile` or documented start commands if Railway prefers config.
- Create: `scripts/seed_demo.py`
- Create: `docs/deployment/railway.md`
- Add tests for demo seed idempotency where practical.

- [ ] **Step 1: Add deployment files and documented env vars**

Include API and worker commands, PostgreSQL/Redis env placeholders, migration command, and frontend build command.

- [ ] **Step 2: Add demo seed**

Seed employee 4명, 1주 schedule, 휴가 1건, 상극 조합 1건, 완화안 케이스.

- [ ] **Step 3: Verify local release commands and commit**

Run backend tests, import checks, and documented command smoke tests.
