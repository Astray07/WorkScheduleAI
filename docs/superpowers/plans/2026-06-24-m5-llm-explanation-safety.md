# M5 LLM Explanation Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for the tests first, then superpowers:executing-plans task-by-task.

**Goal:** Add a template-first LLM explanation safety layer that proves PII is not sent to LLM payloads and fallback is used when provider output is absent, malformed, or distorts server-generated facts.

**Architecture:** Create a small `work_schedule_ai.llm` module. It builds anonymized payloads from structured server facts via whitelist mapping, validates optional structured provider output, and returns the existing `LLMExplanation` shape. ScheduleRun APIs keep using fallback by default.

**Tech Stack:** Python, Pydantic v2, pytest.

---

### Task 1: Tests First

**Files:**
- Create: `tests/llm/test_explanations.py`

- [x] **Step 1: Add privacy test**

Assert anonymized payload excludes employee names, organization names, emails, stable employee codes, notes, prompt injection text, and numeric loss scores.

- [x] **Step 2: Add fallback/schema tests**

Assert malformed provider output returns server-template fallback.

- [x] **Step 3: Add distortion tests**

Assert provider output that references a proposal type or reason code outside the server-provided allowed set is discarded.

### Task 2: Implementation

**Files:**
- Create: `src/work_schedule_ai/llm/__init__.py`
- Create: `src/work_schedule_ai/llm/explanations.py`
- Modify: `src/work_schedule_ai/api/routes/schedule_runs.py`

- [x] **Step 1: Implement anonymized payload builder**

Use request-local aliases `P1`, `P2`, etc. Build a new payload from whitelisted fields only.

- [x] **Step 2: Implement fallback/validation service**

Validate structured JSON output with Pydantic. Return fallback on missing, malformed, distorted, or unsafe data.

- [x] **Step 3: Wire ScheduleRun fallback**

Keep existing API response shape and text stable by sourcing fallback through the new module.

### Task 3: Verification and Commit

- [x] **Step 1: Run focused tests**

```powershell
python -m pytest tests\llm\test_explanations.py -q
python -m pytest tests\api\test_schedule_runs_api.py -q
```

- [x] **Step 2: Run full verification**

```powershell
python -m pytest -q
git diff --check
```

- [x] **Step 3: Commit**

```powershell
git add src/work_schedule_ai/llm src/work_schedule_ai/api/routes/schedule_runs.py tests/llm/test_explanations.py docs/superpowers/plans/2026-06-24-m5-llm-explanation-safety.md work/tasks/2026-06-24-m5-llm-explanation-safety work/tasks/2026-06-24-first-release-execution
git commit -m "feat: add llm explanation safety layer"
```
