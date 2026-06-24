# M0 Contract Freeze Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze the M0 contracts for WorkScheduleAI so frontend, API, DB, and worker work can proceed in parallel.

**Architecture:** M0 produces contract artifacts only: OpenAPI JSON, ScheduleRun state machine, DB migration plan, and mock UI fixtures. The contracts preserve the product decisions that OR-Tools owns scheduling, LLM only explains server-generated structure, ScheduleRun and SchedulePublication are separate, and unfilled requirements are ScheduleIssue records.

**Tech Stack:** OpenAPI 3.1 JSON, FastAPI target API, PostgreSQL target DB, SQLAlchemy/Alembic target migration layer, Redis target queue, React or Next.js target frontend.

---

## File Structure

- Create: `work/tasks/2026-06-24-m0-contract-freeze/brief.md` - M0 goal, non-goals, success criteria, constraints.
- Create: `work/tasks/2026-06-24-m0-contract-freeze/plan.md` - live task checklist.
- Create: `work/tasks/2026-06-24-m0-contract-freeze/decisions.md` - M0 decisions and rejected scope.
- Create: `work/tasks/2026-06-24-m0-contract-freeze/verification.md` - validation commands and outcomes.
- Create: `work/tasks/2026-06-24-m0-contract-freeze/handoff.md` - continuation state.
- Create: `docs/contracts/m0-contract-overview.md` - reader-facing summary of fixed contracts.
- Create: `docs/contracts/openapi.m0.json` - OpenAPI 3.1 draft for P0/M0.
- Create: `docs/contracts/schedule-run-state-machine.md` - ScheduleRun states, transitions, counters, invariants.
- Create: `docs/contracts/m0-db-migration-plan.md` - planned migration sequence and core DB invariants.
- Create: `docs/contracts/fixtures/p0-schedule-run-running.json` - status polling fixture.
- Create: `docs/contracts/fixtures/p0-result-before-relaxation.json` - issue path result fixture.
- Create: `docs/contracts/fixtures/p0-result-after-recalculation.json` - recalculated result fixture.

## Task 1: Work Harness

**Files:**
- Create: `work/tasks/2026-06-24-m0-contract-freeze/brief.md`
- Create: `work/tasks/2026-06-24-m0-contract-freeze/plan.md`
- Create: `work/tasks/2026-06-24-m0-contract-freeze/decisions.md`
- Create: `work/tasks/2026-06-24-m0-contract-freeze/verification.md`
- Create: `work/tasks/2026-06-24-m0-contract-freeze/handoff.md`

- [x] **Step 1: Create the task directory**

Run:

```powershell
New-Item -ItemType Directory -Force 'work\tasks\2026-06-24-m0-contract-freeze' | Out-Null
```

Expected: directory exists.

- [x] **Step 2: Write task harness documents**

Write the five files listed above with M0 scope, non-goals, decisions, validation plan, and handoff state.

- [x] **Step 3: Verify task harness documents exist**

Run:

```powershell
Test-Path 'work\tasks\2026-06-24-m0-contract-freeze\brief.md'
Test-Path 'work\tasks\2026-06-24-m0-contract-freeze\plan.md'
Test-Path 'work\tasks\2026-06-24-m0-contract-freeze\decisions.md'
Test-Path 'work\tasks\2026-06-24-m0-contract-freeze\verification.md'
Test-Path 'work\tasks\2026-06-24-m0-contract-freeze\handoff.md'
```

Expected: all five lines are `True`.

## Task 2: OpenAPI Contract

**Files:**
- Create: `docs/contracts/m0-contract-overview.md`
- Create: `docs/contracts/openapi.m0.json`

- [x] **Step 1: Create contract directories**

Run:

```powershell
New-Item -ItemType Directory -Force 'docs\contracts','docs\contracts\fixtures' | Out-Null
```

Expected: both directories exist.

- [x] **Step 2: Write OpenAPI JSON**

Write `docs/contracts/openapi.m0.json` with these P0 paths:

```text
POST /organizations
POST /organizations/{organization_id}/employees/bulk-paste
POST /organizations/{organization_id}/unavailabilities
POST /organizations/{organization_id}/pair-constraints
POST /organizations/{organization_id}/schedule-runs
GET /organizations/{organization_id}/schedule-runs/{schedule_run_id}
GET /organizations/{organization_id}/schedule-runs/{schedule_run_id}/result
POST /organizations/{organization_id}/schedule-runs/{schedule_run_id}/manual-edits/validate
POST /organizations/{organization_id}/schedule-runs/{schedule_run_id}/relaxation-proposals/{proposal_id}/approve
POST /organizations/{organization_id}/schedule-runs/{schedule_run_id}/recalculate
POST /organizations/{organization_id}/schedule-runs/{schedule_run_id}/publications
GET /organizations/{organization_id}/schedule-publications/{publication_id}/excel
```

Include enums for ScheduleRun status, solution quality, solver status, severity, issue type, reason code, proposal type/status, assignment source, warning state, and publication status.

- [x] **Step 3: Validate OpenAPI JSON parses**

Run:

```powershell
@'
import json
from pathlib import Path
path = Path("docs/contracts/openapi.m0.json")
json.loads(path.read_text(encoding="utf-8"))
print(f"parsed {path}")
'@ | python -
```

Expected: `parsed docs\contracts\openapi.m0.json`.

## Task 3: State Machine And DB Plan

**Files:**
- Create: `docs/contracts/schedule-run-state-machine.md`
- Create: `docs/contracts/m0-db-migration-plan.md`

- [x] **Step 1: Write ScheduleRun state machine**

Document states `queued`, `running`, `succeeded`, `infeasible`, `failed`, `canceled`; allowed transitions; counter semantics; recalculation rules; publication lock behavior.

- [x] **Step 2: Write DB migration plan**

Document table creation order, core constraints, pair normalization, assignment uniqueness, publication overlap exclusion, RLS plan, and M0 deferred migration execution.

- [x] **Step 3: Check required terms are present**

Run:

```powershell
rg -n "queued|running|succeeded|infeasible|failed|canceled|current_attempt_no|recalculation_count|SchedulePublication" docs\contracts\schedule-run-state-machine.md
rg -n "employees\\(organization_id, employee_code\\)|pair_constraints|schedule_publications|RLS|FORCE ROW LEVEL SECURITY" docs\contracts\m0-db-migration-plan.md
```

Expected: each command prints matching lines.

## Task 4: Mock UI Fixtures

**Files:**
- Create: `docs/contracts/fixtures/p0-schedule-run-running.json`
- Create: `docs/contracts/fixtures/p0-result-before-relaxation.json`
- Create: `docs/contracts/fixtures/p0-result-after-recalculation.json`

- [x] **Step 1: Write polling fixture**

Create a `running` ScheduleRun response fixture with progress phase, score summary, empty issues, and empty proposals.

- [x] **Step 2: Write issue path result fixture**

Create a result fixture with 1 week of slots, `사수`/`부사수` requirements, assignments, one `unfilled_requirement` issue, one suggested `approve_pair_constraint_override` proposal, and `read_only: false`.

- [x] **Step 3: Write recalculated result fixture**

Create a result fixture for `recalculation_count: 1` with the approved proposal applied, all requirements filled, warning state on the override assignment, and no active issues.

- [x] **Step 4: Validate fixture JSON parses**

Run:

```powershell
@'
import json
from pathlib import Path
for path in sorted(Path("docs/contracts/fixtures").glob("*.json")):
    json.loads(path.read_text(encoding="utf-8"))
    print(f"parsed {path}")
'@ | python -
```

Expected: each fixture path prints once.

## Task 5: Verification And Handoff

**Files:**
- Modify: `work/tasks/2026-06-24-m0-contract-freeze/verification.md`
- Modify: `work/tasks/2026-06-24-m0-contract-freeze/handoff.md`
- Modify: `work/tasks/2026-06-24-m0-contract-freeze/plan.md`

- [x] **Step 1: Run all M0 verification commands**

Run JSON parsing and required-term checks from Tasks 1-4.

- [x] **Step 2: Update verification.md with exact results**

Record command outcomes, failures, and remaining risks.

- [x] **Step 3: Update plan.md and handoff.md**

Mark completed steps and record the next recommended implementation step: project scaffold selection and API schema generation.
