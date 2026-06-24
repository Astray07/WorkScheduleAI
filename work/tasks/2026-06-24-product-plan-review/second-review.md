# WorkScheduleAI Product Plan Second Review

## Summary

The revised document is materially stronger than the prior version. The biggest previous gaps were addressed:

- `4.1 1차 완성 범위` now gives one priority scope.
- `4.2 P0 Vertical Slice` defines a thin end-to-end path.
- `4.3 1차 릴리즈 제한` adds practical limits.
- `4.4 Milestones And Exit Criteria` makes delivery sequencing clearer.
- `13.1 LLM Output Contract`, `15.1 UI Acceptance Criteria`, `16.5 API Contract Sketch`, `16.6 DB Invariants`, and `16.7 Worker Retry And Idempotency` improve implementation readiness.

The remaining feedback is narrower: a few scope contradictions and contract details should be tightened before implementation.

## High Priority Feedback

### 1. SchedulePublication Is Still Ambiguous In 1차 범위

`4.1` marks `SchedulePublication` as "데이터 모델만 준비" under result review, but the P0 happy path says the admin confirms the result and downloads Excel. Section `11.6` also says final confirmation creates `SchedulePublication`.

Recommendation:

- Either include a minimal `SchedulePublication` implementation in 1차 scope.
- Or rename the P0 action from "확정" to "검토 완료 후 다운로드" and state that true publication/locking is v1.

From a backend and HR audit perspective, exception approval plus final download without a persisted publication record is weak.

### 2. LLM Phase Language Still Conflicts

`4.1` includes "서버 구조화 데이터 기반 LLM 설명" in 1차 scope, and `18.1` includes LLM explanation in success criteria. But `6.3` still says "v1 이후 LLM은 서버가 만든 구조화 데이터를 관리자용 문장으로 바꿉니다."

Recommendation:

- Change `6.3` to say that 1차 includes optional/asynchronous LLM explanation with server fallback.
- Keep "LLM 설명 고도화" in v1 for richer copy, upload error explanations, or model evaluation expansion.

### 3. 1주 Scope Versus 31일 Limit Needs One Sentence

`4.1` says 1차 includes "1주 단위 생성", while `4.3` says maximum generation period is 31 days. These can coexist, but the intended meaning should be explicit.

Recommendation:

- Define "P0 demo path is 1 week; 1차 릴리즈 UI/API allows up to 31 days with performance guarantee only for 30 employees."
- Or reduce 1차 maximum to 7 days and move 31 days to v1.

### 4. API Sketch Cannot Yet Render The Result Grid

`16.5` sketches ScheduleRun, Issue, Proposal, and manual validation responses, but the frontend still needs assignments and slots to render the result grid described in `15.1`.

Recommendation:

- Add a `ScheduleRunResult` or `GET /schedule-runs/{id}/result` response with `slots`, `requirements`, `assignments`, and `issues`.
- Include enough fields for the grid: local date, slot label, role id/name, employee id/name, source, warning state, and publication/read-only state.

### 5. DB Assignment Invariants Need One More Unique Rule

`16.6` has `assignments(schedule_run_id, shift_slot_id, role_id, employee_id)` unique. This does not by itself prevent the same employee from being assigned to two roles in the same slot.

Recommendation:

- Add `assignments(schedule_run_id, shift_slot_id, employee_id)` unique if one employee can never fill multiple roles in the same slot.
- If exceptions are possible, state the exception explicitly and keep it in solver/manual validation.

Also define whether `normalized_employee_a_id` and `normalized_employee_b_id` are generated columns, write-time normalized values, or enforced by a check constraint.

## Medium Priority Feedback

### 6. Test Strategy Has Not Fully Caught Up

The new plan adds bulk paste, UI state criteria, DB invariants, worker idempotency, and LLM schema validation, but section `19` still has the older, shorter test list.

Recommendation:

- Add tests for bulk paste validation.
- Add API tests for idempotency key conflict and retry cleanup.
- Add DB tests for pair constraint normalization and same-slot duplicate employee assignment.
- Add frontend tests for ScheduleRun state rendering and manual edit validation.
- Add LLM schema-validation fallback tests.

### 7. Idempotency Conflict Case Is Missing

`16.7` says same organization, same snapshot hash, same idempotency key returns existing ScheduleRun. It does not say what happens when the same idempotency key arrives with a different snapshot hash.

Recommendation:

- Return `409 Conflict` or create a new run only when the idempotency key differs.
- Document the expected API behavior because frontend retry logic depends on it.

### 8. HR Notification Record Is Good, But Approval Alternatives Need Structure

`14.5` says approval records include selected alternative and notification status. This is valuable, but the model currently stores `reason` and `target_json`; the "rejected alternatives" or "selected alternative" shape is not explicit.

Recommendation:

- Add fields or metadata convention for `considered_proposal_ids`, `selected_proposal_id`, `notification_required`, and `notification_recorded_by`.

### 9. Bulk Paste Is The Right MVP Compromise, But It Needs A Template Contract

Bulk paste solves the HR onboarding gap without full `.xlsx` upload. It still needs a concrete column contract.

Recommendation:

- Add the 1차 paste column sets for employees, unavailability, and pair constraints.
- Keep them aligned with the future Excel upload templates.

## Role-Based Delta

Frontend developer:
The UI criteria are now much better. Remaining need: result payload shape with assignments and slot metadata.

Backend developer:
The schema and worker sections are much stronger. Remaining need: publication scope, duplicate assignment rule, idempotency conflict behavior.

Full-stack developer:
The vertical slice is now implementable. Remaining need: clarify whether "confirm" means persisted publication or only export-ready result.

Development team lead:
Milestones are now useful. Remaining need: update test strategy to match the new milestone risks.

AI team lead:
LLM output contract is much improved. Remaining need: JSON Schema enums, fallback test cases, and phase wording cleanup.

AX team leader:
Adoption metrics and Excel onboarding are now present. Remaining need: paste template shape and measurable before/after baseline.

UI/UX web design team lead:
Operational UI direction is now correct. Remaining need: result grid data contract and visual distinction between draft, approved exception, and published states.

HR team lead candidate:
The plan is more credible now. Remaining concern is auditability: final confirmed schedule and exception decisions should be durable, not just downloadable.

## Suggested Next Edits

1. Decide whether minimal `SchedulePublication` is in 1차.
2. Fix `6.3` LLM phase wording.
3. Clarify 1-week P0 versus 31-day max.
4. Add result grid API response.
5. Add same-slot duplicate employee assignment invariant.
6. Expand section `19` tests to cover new scope.
