# Release Feedback Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for behavior changes and superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Address release-review P0/P1 blockers by moving ScheduleRun execution to a persisted solver-result path and making the P0 frontend exercise shift-template solver flow.

**Architecture:** Add persisted result artifact tables and immutable publication snapshot JSON. ScheduleRun creation and recalculation call the worker with an executor callback that computes solver/mock artifacts once and stores them. Result reads, publication, and Excel export load stored artifacts instead of recomputing from mutable organization data.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, OR-Tools CP-SAT, React/Vite.

---

### Task 1: Regression Tests

**Files:**
- Modify: `tests/api/test_schedule_runs_api.py`
- Modify: `tests/api/test_p0_vertical_slice_api.py`
- Modify: `tests/worker/test_schedule_worker.py`

- [x] **Step 1: Add idempotency conflict test**

Assert same `Idempotency-Key` with a different period returns `409 SCHEDULE_RUN_IDEMPOTENCY_CONFLICT`.

- [x] **Step 2: Add persisted result test**

Assert shift-template ScheduleRun creates stored slots, assignments, and uses `cp_sat_*` solver status.

- [x] **Step 3: Add immutable publication test**

Publish a run, mutate employee names, download Excel, and assert the original name remains in the workbook.

### Task 2: Persisted Artifacts

**Files:**
- Modify: `src/work_schedule_ai/db/models.py`
- Create: `alembic/versions/20260624_0008_m1_schedule_result_artifacts.py`
- Modify: `src/work_schedule_ai/api/routes/schedule_runs.py`

- [x] **Step 1: Add models and migration**

Add `ShiftSlot`, `Assignment`, `ScheduleIssue`, `RelaxationProposal`, and `SchedulePublication.result_snapshot_json`.

- [x] **Step 2: Store computed artifacts**

Persist slots, assignments, issues, proposals, and score summary after worker execution.

- [x] **Step 3: Load stored artifacts**

Convert stored rows back to existing response models for result/status/publication/download.

### Task 3: Worker And Snapshot

**Files:**
- Modify: `src/work_schedule_ai/worker/schedule_worker.py`
- Modify: `src/work_schedule_ai/api/routes/schedule_runs.py`

- [x] **Step 1: Worker executor callback**

Allow `execute_schedule_run(session, run_id, executor=...)` and set final status from executor-updated run fields.

- [x] **Step 2: Full input snapshot**

Include shift types, requirements, employees, employee roles, unavailabilities, and pair constraints in `ScheduleInputSnapshot.payload_json`.

- [x] **Step 3: Idempotency conflict**

Compare the new snapshot hash with existing run hash before returning idempotent existing runs.

### Task 4: Frontend And Deploy

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `pyproject.toml`

- [x] **Step 1: Create shift type in P0 flow**

After organization and employees are created, create a `주간 근무` shift type with `사수` and `부사수` requirements.

- [x] **Step 2: Add PostgreSQL driver**

Add `psycopg[binary]` to deploy dependencies.

### Task 5: Verification And Commit

- [x] **Step 1: Run focused tests**

Run the focused pytest commands listed in the task harness.

- [x] **Step 2: Run full verification**

Run full pytest, frontend build, browser smoke, and `git diff --check`.

- [x] **Step 3: Commit**

Commit only remediation files, excluding pre-existing review document changes.
