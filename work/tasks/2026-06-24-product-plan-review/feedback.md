# WorkScheduleAI Product Plan Feedback

## Overall Assessment

The plan is strong in its core technical stance: OR-Tools owns scheduling, the server owns relaxation candidates, and LLM is limited to explanation. That separation reduces product and privacy risk.

The main weakness is execution readiness. The document describes a fairly mature SaaS, but the immediate build scope is not fully aligned across the phase table, screen list, architecture, and success criteria. Before development starts, the team should define one unambiguous "1차 완성" contract.

## Highest Priority Revisions

1. Align scope language.
   - Lines 41-51 say 1차 완성 includes MVP plus v1 `LLM 설명 보조` and `예외 승인 후 재계산`.
   - Line 45 says MVP excludes LLM.
   - Lines 1003-1004 include LLM in 1차 success criteria.
   - Recommendation: create one table named `1차 완성 범위` with included, excluded, and data-model-only items.

2. Define the thinnest end-to-end slice.
   - A credible first slice should be: organization, employees, roles, shift template, unavailability, pair block, schedule run, result grid, relaxation proposal, approval, recalculation, Excel download.
   - Everything else should be behind explicit phase gates.

3. Add API and UI acceptance criteria.
   - The plan lists modules and screens, but does not define endpoint contracts, UI states, validation errors, polling behavior, or manual edit rules.

4. Add operational limits.
   - Define maximum scheduling period, recommended employee count for first release, solver timeout defaults, background job retry/cancel behavior, and expected response states.

5. Add adoption metrics for HR buyers.
   - HR will care about time saved, fairness explainability, privacy, exception auditability, and how well the system preserves existing Excel workflows.

## Frontend Developer Perspective

The screen list is useful, but not detailed enough to implement confidently. The schedule result page needs explicit UI states: queued, running, feasible, feasible-not-optimal, infeasible, canceled, failed, approved exception pending recalculation, and published.

The grid behavior is underspecified. The plan should define whether assignments are cell-based, slot-based, role-column-based, draggable, inline editable, or modal-driven. Manual adjustment is mentioned, but the validation behavior after manual edits is not defined.

Frontend needs stable response shapes for ScheduleRun, ScheduleIssue, RelaxationProposal, and quality score breakdown. Without that, the result screen and explanation panel will drift from backend reality.

## Backend Developer Perspective

The domain model is thoughtful, especially snapshots, RLS, ScheduleRun, ScheduleIssue, and publication separation. The missing pieces are database invariants and transactional rules.

The spec should add unique constraints and indexes for tenant-scoped natural keys, symmetric pair constraints, publication uniqueness by organization and period, assignment uniqueness by run/slot/role/employee, and overlap lookup indexes for unavailability.

The worker flow needs idempotency details. If a queued job is retried, the backend must define whether it reuses the same ScheduleRun, replaces partial assignments, appends diagnostics, or marks the prior attempt failed.

## Full-Stack Developer Perspective

The plan has strong vertical concepts but weak slice boundaries. Full-stack implementation needs one exact happy path and one exact failure path before broad feature work.

Recommended first vertical slice: create organization, seed default roles, add 4 employees, add one vacation and one blocked pair, generate a one-week schedule, show missing/relaxation output, approve one proposal, recalculate, download Excel.

Excel upload should stay out of the first slice if the table says it is v1. Excel download can remain in MVP, but the export format should be fixed early because HR users will judge the product through that file.

## Development Team Lead Perspective

The plan is technically ambitious for a first delivery. RLS, Redis worker, OR-Tools modeling, diagnostics, LLM explanation, Excel, deployment, and a full admin UI are all meaningful work streams.

The team lead should turn this into milestones with owners and exit criteria. Suggested milestones: domain schema and tenant safety, deterministic solver golden cases, schedule run API and worker, admin setup UI, result/exception UI, LLM explanation, Railway deployment hardening.

The risk section is good, but it needs mitigation triggers. For example: if 100-person monthly schedules exceed timeout, reduce max period; if infeasibility diagnosis is unstable, ship server-only structured explanations before LLM.

## AI Team Lead Perspective

The AI boundary is appropriate. LLM should not decide assignments or generate original relaxation candidates.

The plan needs an LLM output contract. Define schema, allowed phrases, forbidden claims, fallback templates, and validation checks that prevent the model from inventing causes or overstating optimality.

The privacy design is strong, especially request-level pseudonyms. The next step is an evaluation set: anonymization leakage tests, prompt injection tests from uploaded Excel text, explanation faithfulness tests, and small-organization re-identification review.

## AX Team Leader Perspective

From an AI transformation and adoption angle, the plan should explain how the service changes the current Excel-based work process. The product should not only generate schedules; it should reduce coordination cost and make exceptions easier to justify.

The plan needs onboarding and change-management flows: import or copy existing employees, start from a familiar template, compare generated schedule with previous manual schedule, and export a format acceptable to current stakeholders.

AX success metrics should be added: schedule creation time reduction, number of manual edits after generation, exception approval rate, HR satisfaction, employee dispute count, and repeat usage by the same organization.

## UI/UX Web Design Team Lead Perspective

The product needs a dense operational UI, not a marketing-style AI interface. The first screen after organization setup should help an admin complete setup and generate a schedule, not read about features.

The most important design surface is the schedule result and exception review screen. It should show schedule grid, unfilled slots, conflict reasons, recommendation rank, approval impact, and recalculation action in one coherent workflow.

The plan should define empty states, validation states, disabled states, and conflict severity visuals. The user must be able to trust why the system made a recommendation before approving an exception.

## HR Team Lead Candidate User Perspective

As an HR team lead, I would find the concept valuable because it addresses real pain: vacation conflicts, fairness complaints, pair restrictions, and repetitive Excel work.

I would hesitate if Excel upload is not available early, because initial data entry for 50-100 employees through screens may be too slow. If upload remains v1, the MVP should at least provide fast copy-paste entry or a very efficient bulk entry grid.

I would also need clearer assurances about privacy, audit trails, and exception accountability. If the system recommends assigning someone during vacation or breaking a pair constraint, I need a record of who approved it, why, and what alternative was rejected.

The plan should avoid implying legal compliance. It correctly excludes full legal guarantees, but HR will still expect configurable guardrails for rest time, consecutive work, weekends, and local policy.

## Suggested Document Edits

1. Add a `1차 완성 범위` table that overrides MVP/v1 ambiguity.
2. Add a `P0 vertical slice` section with one happy path and one infeasible path.
3. Add API contract sketches for the scheduling flow.
4. Add UI acceptance criteria for result grid, issue list, proposal review, and manual edit.
5. Add database invariants and worker idempotency rules.
6. Add LLM schema, evaluation set, and fallback behavior.
7. Add HR adoption metrics and onboarding workflow.
8. Add explicit release limits: employee count, schedule period, timeout, and unsupported cases.
