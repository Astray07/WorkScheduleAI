# M3 Schedule Worker State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an in-process ScheduleRun worker adapter with state transition, cancel, and technical retry semantics.

**Architecture:** Keep Redis/Railway worker deployment for a later deployment step. The worker module will operate on SQLAlchemy sessions and can later be called by a queue consumer; API creation will enqueue as `queued` and immediately execute in-process for local MVP behavior.

**Tech Stack:** FastAPI, SQLAlchemy 2, pytest.

---

### Task 1: Failing Worker and API Tests

**Files:**
- Add: `tests/worker/test_schedule_worker.py`
- Modify: `tests/api/test_schedule_runs_api.py`

- [x] **Step 1: Add worker state transition tests**

Test `queued -> running -> succeeded`, canceling a queued run, skipping execution for canceled runs, and technical retry incrementing `current_attempt_no` without changing `recalculation_count`.

- [x] **Step 2: Add cancel API tests**

Test `POST /organizations/{organization_id}/schedule-runs/{schedule_run_id}/cancel` cancels queued runs and rejects succeeded runs.

- [x] **Step 3: Run RED verification**

Run:

```powershell
python -m pytest tests/worker/test_schedule_worker.py tests/api/test_schedule_runs_api.py -q
```

Expected: fail because worker module and cancel route do not exist.

### Task 2: Worker Module and API

**Files:**
- Add: `src/work_schedule_ai/worker/__init__.py`
- Add: `src/work_schedule_ai/worker/schedule_worker.py`
- Modify: `src/work_schedule_ai/api/routes/schedule_runs.py`

- [x] **Step 1: Implement worker functions**

Add `execute_schedule_run`, `retry_schedule_run`, and `cancel_schedule_run`.

- [x] **Step 2: Update create ScheduleRun flow**

Persist the run as `queued`, then execute it in-process before returning the current API response.

- [x] **Step 3: Add cancel endpoint**

Add `POST /organizations/{organization_id}/schedule-runs/{schedule_run_id}/cancel`.

- [x] **Step 4: Run focused tests**

Run:

```powershell
python -m pytest tests/worker/test_schedule_worker.py tests/api/test_schedule_runs_api.py -q
```

Expected: pass.

### Task 3: Verification and Commit

**Files:**
- Modify: `work/tasks/2026-06-24-m3-schedule-worker-state/verification.md`
- Modify: `work/tasks/2026-06-24-m3-schedule-worker-state/handoff.md`

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
git add src/work_schedule_ai/worker src/work_schedule_ai/api/routes/schedule_runs.py tests/worker tests/api/test_schedule_runs_api.py docs/superpowers/plans/2026-06-24-m3-schedule-worker-state.md work/tasks/2026-06-24-m3-schedule-worker-state
git commit -m "feat: add schedule worker state transitions"
```
