# M1 P0 Vertical Slice API Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one end-to-end API test that proves the P0 mock flow works from organization creation through Excel download.

**Architecture:** This is a test-only safety net. It uses the FastAPI app with an in-memory SQLite DB and calls public HTTP endpoints in the same sequence an MVP demo would use.

**Tech Stack:** FastAPI TestClient, SQLAlchemy in-memory SQLite, pytest, Python `zipfile`.

---

### Task 1: Add P0 API Flow Test

**Files:**
- Add: `tests/api/test_p0_vertical_slice_api.py`

- [x] **Step 1: Write the integration test**

Create one test that performs:
1. `POST /organizations`
2. `POST /organizations/{organization_id}/employees/bulk-paste`
3. `POST /organizations/{organization_id}/unavailabilities`
4. `POST /organizations/{organization_id}/pair-constraints`
5. `POST /organizations/{organization_id}/schedule-runs`
6. `GET /organizations/{organization_id}/schedule-runs/{schedule_run_id}/result`
7. `POST /organizations/{organization_id}/schedule-runs/{schedule_run_id}/relaxation-proposals/{proposal_id}/approve`
8. `POST /organizations/{organization_id}/schedule-runs/{schedule_run_id}/recalculate`
9. `POST /organizations/{organization_id}/schedule-runs/{schedule_run_id}/publications`
10. `GET /organizations/{organization_id}/schedule-publications/{publication_id}/excel`

- [x] **Step 2: Run focused verification**

Run:

```powershell
python -m pytest tests/api/test_p0_vertical_slice_api.py -q
```

Expected: pass, unless a real integration gap is found.

### Task 2: Final Verification and Commit

**Files:**
- Modify: `work/tasks/2026-06-24-m1-p0-vertical-slice-api-test/verification.md`
- Modify: `work/tasks/2026-06-24-m1-p0-vertical-slice-api-test/handoff.md`

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
git add tests/api/test_p0_vertical_slice_api.py docs/superpowers/plans/2026-06-24-m1-p0-vertical-slice-api-test.md work/tasks/2026-06-24-m1-p0-vertical-slice-api-test
git commit -m "test: add p0 vertical slice api coverage"
```

Expected: commit succeeds on `feature/m1-scaffold-contract-tests`.
