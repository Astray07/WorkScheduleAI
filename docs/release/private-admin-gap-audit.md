# WorkScheduleAI Private Admin Gap Audit

Date: 2026-06-26
Branch: `feature/m1-scaffold-contract-tests`

## Verdict

WorkScheduleAI is now a strong private-admin operating build candidate for local or controlled staging validation.

It is not a public SaaS launch candidate. Public URL, external pilot, or production use still requires authentication, request organization context hardening, real Redis worker-path staging validation, and operational deployment checks.

## Implemented Scope

### Admin Reference Data
- Organization creation and default role setup.
- Employee and role eligibility management.
- Unavailability management for vacation, business trip, training, and personal schedules.
- Pair constraint management for blocked, avoid, and prefer relationships.
- Shift type and role requirement management.
- Schedule policy management.

### Import
- CSV/TSV preview and apply remain supported.
- Official `.xlsx` preview and apply are implemented for employees, unavailabilities, pair constraints, policies, and shift types.
- `.xlsx` preview reports sheet, row number, column, error code, and message.
- Invalid rows block apply.
- Valid rows apply through natural-key upsert behavior where the target supports it.
- Sheet/column contract is documented in `docs/release/import-xlsx-contract.md`.

### Scheduling
- OR-Tools remains the schedule generation engine.
- LLM remains an explanation layer with fallback behavior, not the schedule decision engine.
- Schedule periods are 1-31 days inclusive.
- Scenario-generated shift type sync respects weekday coverage, including weekday-night-only cases without weekend slots.
- Unfilled requirements are soft penalties surfaced as `ScheduleIssue`, not hard solver failure.
- Recalculation keeps approved overrides and manual locks, with `recalculation_count` capped at 3.
- `current_attempt_no` remains worker technical attempt state, separate from administrator recalculation rounds.

### Solver Hardening
- A deterministic 50 employee / 31 day regression remains in default tests.
- A deterministic 100 employee / 31 day high-constraint benchmark exists behind an explicit opt-in environment flag.
- The high-constraint benchmark checks role eligibility, unavailable slots, blocked pairs, weekly caps, max consecutive, min rest, weekend cap, night cap, requirement counts, and expected soft unfilled issue behavior.

### Review And Operations UI
- Operator console supports scenario configuration, reference data management, policy editing, import preview/apply, schedule generation, manual assignment edits, validation, audit visibility, recalculation, publication, and Excel download.
- Current run fairness summary is visible separately from long-term fairness.
- Schedule run history comparison is implemented for assignments, manual locks, issues, and fairness deltas.
- Long-term fairness dashboard is implemented for publications or runs with period filtering, assignment count, night count, weekend count, role counts, and average deltas.
- Operations metrics and readiness endpoints exist for local and staging checks.
- PostgreSQL tenant context hook exists, but full public authentication and membership enforcement remain release gates.

### Publication And Auditability
- `ScheduleRun` and `SchedulePublication` remain separate.
- Publication stores an immutable result snapshot.
- Publication Excel export uses the snapshot.
- Manual assignment saves and publication creation write audit log entries.

## Intentional Exclusions For Private Admin Build

### General User Vacation Or Schedule Requests
Status: excluded.

Reason: the current operating build is admin-entered data only. General user request workflows require user identity, employee-user linking, request state machines, approval queues, and notification behavior.

Risk: admins must manually enter or import requests. This is acceptable for controlled private validation but not for self-service staff rollout.

### Organization Invitations And Multi-User Onboarding
Status: excluded.

Reason: private admin operation assumes a trusted operator context. Invitations require account lifecycle, membership authorization, email delivery, and abuse controls.

Risk: multiple real admins cannot safely self-serve access. Public or multi-admin staging must add authentication and membership enforcement before use.

### Notifications
Status: excluded.

Reason: the product currently records whether notification is required for override approval, but does not send email, Slack, or in-app notifications.

Risk: communication remains manual. This is acceptable for private operator validation, but not for autonomous workflow adoption.

### Public Signup
Status: excluded.

Reason: public signup changes the threat model. It requires authentication, tenant isolation enforcement at every endpoint, rate limits, email verification, account recovery, and abuse handling.

Risk: the app must not be exposed as a public self-serve SaaS until this is implemented and tested.

### Payments
Status: excluded.

Reason: billing is outside the private operations validation path and would add account, subscription, tax, invoice, and entitlement complexity.

Risk: no commercial self-serve launch path exists yet.

### External HR Integrations
Status: excluded.

Reason: `.xlsx` and manual/reference-data APIs are sufficient for private validation. External HR sync requires mapping, credential storage, conflict handling, audit semantics, and data protection review.

Risk: data freshness depends on admin import or manual updates.

### Payroll, Attendance, And Legal Auto-Judgment
Status: excluded.

Reason: the current solver enforces configured scheduling constraints; it does not make legal, payroll, or compliance determinations.

Risk: operators must review results against local labor rules and internal policy.

## Remaining Release Risks

- Authentication and tenant access control are still release gates for any public URL or real external pilot.
- Railway/API/worker/PostgreSQL/Redis staging validation must be run before calling the build production-ready.
- The 100 employee / 31 day hardening benchmark is opt-in, not a default CI runtime gate.
- Publication-snapshot long-term fairness parses JSON at request time; this is acceptable for private validation but may need an aggregate table for large historical datasets.
- Long-term fairness currently uses active employees as the row universe, so historical reports can change if employees are deactivated later.
- Browser smoke tests used mocked APIs for UI rendering where appropriate; real Redis-backed end-to-end staging smoke remains separate.
- Current release posture should be described as a local integration candidate for private-admin validation, not a launch-ready public service.

## Verification Evidence

Latest full verification will be recorded in `work/tasks/2026-06-26-final-gap-audit/verification.md`.

Current expected final gate:
- `python -m pytest -q`
- all `frontend/src/*.test.mjs`
- `npm run build`
- `git diff --check`
- `git rev-list --left-right --count "HEAD...@{u}"`

## Related Commits

- `da47e98 feat: add xlsx import preview`
- `2af69c2 test: add high constraint solver benchmark`
- `1ea0227 feat: add schedule run comparison`
- `2afae9d feat: add long term fairness dashboard`
