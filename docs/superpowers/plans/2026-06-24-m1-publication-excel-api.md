# M1 Publication Excel API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the minimal SchedulePublication creation and Excel download API needed to complete the P0 mock vertical slice.

**Architecture:** Keep ScheduleRun as execution history and add SchedulePublication as the immutable published result pointer. The mock result remains generated from the ScheduleRun; publication stores assignment and issue snapshot hashes so the publish request can detect stale UI state. Excel output is generated with the Python standard library as a small `.xlsx` package to avoid adding a dependency before the export format is stable.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy 2, Alembic, pytest, Python `zipfile`/XML.

---

### Task 1: Contract Tests for Publication and Excel

**Files:**
- Modify: `tests/api/test_schedule_runs_api.py`

- [x] **Step 1: Add failing tests**

Add tests that:
- create and recalculate the P0 mock run,
- read `assignment_snapshot_hash` and `issue_snapshot_hash` from the result,
- publish the run,
- assert the result becomes read-only and includes the publication,
- reject a duplicate overlapping active publication,
- download an `.xlsx` file and verify it is a zip workbook with schedule data.

- [x] **Step 2: Run RED verification**

Run:

```powershell
python -m pytest tests/api/test_schedule_runs_api.py -q
```

Expected: fail because publication fields, publication route, and Excel route do not exist yet.

### Task 2: SchedulePublication DB Model and Migration

**Files:**
- Modify: `src/work_schedule_ai/db/models.py`
- Modify: `src/work_schedule_ai/db/__init__.py`
- Add: `alembic/versions/20260624_0006_m1_schedule_publications.py`
- Modify: `tests/db/test_domain_models.py`
- Modify: `tests/db/test_alembic_migrations.py`

- [x] **Step 1: Add failing DB tests**

Add tests for:
- `SchedulePublication.status` accepts only `published` or `archived`,
- one `ScheduleRun` can have only one publication,
- migration head creates `schedule_publications`,
- migration head is `20260624_0006`.

- [x] **Step 2: Run RED verification**

Run:

```powershell
python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py -q
```

Expected: fail because `SchedulePublication` and migration 0006 do not exist yet.

- [x] **Step 3: Implement minimal model and migration**

Create `schedule_publications` with:
- `id`, `organization_id`, `schedule_run_id`,
- `period_start`, `period_end`,
- `status`,
- `assignment_snapshot_hash`, `issue_snapshot_hash`,
- `published_at`, `created_at`,
- unique `schedule_run_id`,
- check constraints for status and period order.

- [x] **Step 4: Run DB tests**

Run:

```powershell
python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py -q
```

Expected: pass.

### Task 3: Publish and Excel Routes

**Files:**
- Modify: `src/work_schedule_ai/api/routes/schedule_runs.py`

- [x] **Step 1: Add response fields and publish route**

Add:
- `assignment_snapshot_hash` and `issue_snapshot_hash` to result response,
- `SchedulePublicationResponse`,
- `PublishScheduleRunRequest`,
- `POST /organizations/{organization_id}/schedule-runs/{schedule_run_id}/publications`.

Publication rules:
- run must exist and belong to the organization,
- expected hashes must match current mock result,
- issues must be empty for the P0 publish path,
- same run cannot be published twice,
- another `published` publication with overlapping period in the organization returns 409.

- [x] **Step 2: Add Excel route**

Add:
- `GET /organizations/{organization_id}/schedule-publications/{publication_id}/excel`,
- 404 for missing publication,
- `.xlsx` response with schedule rows from the published run,
- headers suitable for browser download.

- [x] **Step 3: Run API tests**

Run:

```powershell
python -m pytest tests/api/test_schedule_runs_api.py -q
```

Expected: pass.

### Task 4: Final Verification and Commit

**Files:**
- Modify: `work/tasks/2026-06-24-m1-publication-excel-api/verification.md`
- Modify: `work/tasks/2026-06-24-m1-publication-excel-api/handoff.md`

- [x] **Step 1: Run full verification**

Run:

```powershell
python -m pytest -q
git diff --check
git status --short --branch
```

Expected: all tests pass, whitespace check passes, status shows only intended files before commit.

- [x] **Step 2: Commit**

Run:

```powershell
git add docs/superpowers/plans/2026-06-24-m1-publication-excel-api.md work/tasks/2026-06-24-m1-publication-excel-api src tests alembic
git commit -m "feat: add schedule publication excel export api"
```

Expected: commit succeeds on `feature/m1-scaffold-contract-tests`.
