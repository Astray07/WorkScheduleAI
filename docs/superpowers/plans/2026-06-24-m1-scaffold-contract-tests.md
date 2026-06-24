# M1 Scaffold Contract Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the first Python package scaffold and contract tests for the M0 OpenAPI and mock fixtures.

**Architecture:** This step adds a small Python package that loads JSON contract files from `docs/contracts` and exposes validation helpers. Tests assert the P0 paths, core schemas, and mock result fixture states so future API, worker, and frontend work starts from the same contract.

**Tech Stack:** Python 3.13, pytest, standard-library JSON/pathlib.

---

## File Structure

- Create: `pyproject.toml` - package metadata and pytest configuration.
- Create: `src/work_schedule_ai/__init__.py` - package marker and version.
- Create: `src/work_schedule_ai/contracts.py` - M0 contract loading and validation helpers.
- Create: `tests/contracts/test_m0_contract.py` - contract tests written first.
- Create: `work/tasks/2026-06-24-m1-scaffold-contract-tests/*.md` - task harness documents.

## Task 1: Write Contract Tests First

**Files:**
- Create: `tests/contracts/test_m0_contract.py`

- [x] **Step 1: Write failing tests**

Create tests that import these not-yet-existing helpers:

```python
from work_schedule_ai.contracts import (
    CORE_M0_SCHEMAS,
    P0_REQUIRED_PATHS,
    fixture_names,
    load_fixture,
    load_openapi_contract,
    missing_core_schemas,
    missing_p0_paths,
)


def test_openapi_contract_contains_p0_paths():
    contract = load_openapi_contract()

    assert missing_p0_paths(contract) == []
    assert len(P0_REQUIRED_PATHS) == 12


def test_openapi_contract_contains_core_schemas():
    contract = load_openapi_contract()

    assert missing_core_schemas(contract) == []
    assert "ScheduleRunResponse" in CORE_M0_SCHEMAS
    assert "ScheduleRunResultResponse" in CORE_M0_SCHEMAS


def test_fixture_set_contains_p0_states():
    names = fixture_names()

    assert names == [
        "p0-result-after-recalculation.json",
        "p0-result-before-relaxation.json",
        "p0-schedule-run-running.json",
    ]


def test_running_fixture_is_pollable_schedule_run():
    payload = load_fixture("p0-schedule-run-running.json")

    assert payload["status"] == "running"
    assert payload["current_attempt_no"] == 1
    assert payload["recalculation_count"] == 0
    assert payload["issues"] == []
    assert payload["proposals"] == []


def test_issue_fixture_exposes_unfilled_requirement_and_proposal():
    payload = load_fixture("p0-result-before-relaxation.json")

    assert payload["status"] == "infeasible"
    assert payload["read_only"] is False
    assert payload["issues"][0]["type"] == "unfilled_requirement"
    assert payload["issues"][0]["missing_count"] == 1
    assert payload["proposals"][0]["type"] == "approve_pair_constraint_override"
    assert payload["proposals"][0]["status"] == "suggested"


def test_recalculated_fixture_keeps_counters_distinct():
    payload = load_fixture("p0-result-after-recalculation.json")

    assert payload["status"] == "succeeded"
    assert payload["current_attempt_no"] == 2
    assert payload["recalculation_count"] == 1
    assert payload["issues"] == []
    assert any(
        assignment["source"] == "override"
        and assignment["warning_state"] == "approved_override"
        for assignment in payload["assignments"]
    )
```

- [x] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/contracts/test_m0_contract.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'work_schedule_ai'`.

## Task 2: Add Minimal Package Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `src/work_schedule_ai/__init__.py`
- Create: `src/work_schedule_ai/contracts.py`

- [x] **Step 1: Write minimal package configuration**

`pyproject.toml` must include editable package discovery under `src` and pytest path configuration.

- [x] **Step 2: Implement contract helpers**

`contracts.py` should use only `json` and `pathlib`, calculate the repository root from `__file__`, load `docs/contracts/openapi.m0.json`, list fixture names, load fixtures, and return missing path/schema lists.

- [x] **Step 3: Run contract tests and verify GREEN**

Run:

```powershell
python -m pytest tests/contracts/test_m0_contract.py -q
```

Expected: 6 tests pass.

## Task 3: Verify And Commit

**Files:**
- Modify: `work/tasks/2026-06-24-m1-scaffold-contract-tests/verification.md`
- Modify: `work/tasks/2026-06-24-m1-scaffold-contract-tests/handoff.md`
- Modify: `work/tasks/2026-06-24-m1-scaffold-contract-tests/plan.md`

- [x] **Step 1: Run full test suite**

Run:

```powershell
python -m pytest -q
```

Expected: all tests pass.

- [x] **Step 2: Update task documents**

Record RED/GREEN output and remaining risks.

- [x] **Step 3: Commit changes**

Run:

```powershell
git add pyproject.toml src tests docs/superpowers/plans work/tasks/2026-06-24-m1-scaffold-contract-tests
git commit -m "test: add m0 contract test scaffold"
```

Expected: commit is created on `feature/m1-scaffold-contract-tests`.
