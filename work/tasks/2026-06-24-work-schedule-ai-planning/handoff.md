# Handoff

## 현재 상태

WorkScheduleAI 기획서 초안을 작성했고, 외부 피드백을 반영해 수정했습니다.

메인 산출물:

- `docs/superpowers/specs/work-schedule-ai-product-plan.md`

보조 기록:

- `work/tasks/2026-06-24-work-schedule-ai-planning/brief.md`
- `work/tasks/2026-06-24-work-schedule-ai-planning/plan.md`
- `work/tasks/2026-06-24-work-schedule-ai-planning/decisions.md`
- `work/tasks/2026-06-24-work-schedule-ai-planning/verification.md`

## 다음 단계

1. 사용자가 기획서 초안을 리뷰합니다.
2. 수정 요청이 있으면 반영합니다.
3. 기획서가 승인되면 `superpowers:writing-plans`를 사용해 구현 계획을 작성합니다.

## 반영된 주요 피드백

- 제약 분류를 `절대 불가/승인 시 완화 가능/점수 기반 최적화`로 수정했습니다.
- MVP, v1, v2 범위를 분리했습니다.
- ScheduleRun에 재현성 필드를 추가했습니다.
- 실패 진단을 후보 제거 로그와 assumption/enforcement literal 기반 진단 모델로 구체화했습니다.
- FairnessLedger, ImportBatch, AuditLog, EmployeeUserLink를 추가했습니다.
- Railway 배포를 API와 solver worker 분리 구조로 수정했습니다.
- 2차 피드백으로 ScheduleIssue, SchedulePublication, ScheduleInputSnapshot, SolverDiagnosticEvent를 추가했습니다.
- 연속근무/최소휴식은 승인 시 완화 가능 제약으로 통일했습니다.
- 완화안은 인스턴스 단위 enforcement literal과 묶음 승인 group_id를 전제로 정리했습니다.
- 최종 피드백으로 미배정은 승인 필요 hard 제약이 아니라 soft penalty로 정리했습니다.
- 역할별 미배정 가중치는 SchedulePolicyRoleWeight와 ShiftRequirement override로 표현합니다.
- 1차 완성 성공 기준과 후속 v1/v2 성공 기준을 분리했습니다.
- 다관점 피드백으로 1차 완성 범위 표와 P0 vertical slice를 추가했습니다.
- API 응답 초안, UI acceptance criteria, DB invariant, worker idempotency, LLM schema/eval/fallback, HR 도입 지표를 추가했습니다.
- 2차 다관점 피드백으로 SchedulePublication을 1차 범위에 포함했습니다.
- 재계산은 override/manual lock을 고정하고 recalculation_count를 증가시키며 최대 3라운드까지만 수행합니다.
- 결과 그리드용 `GET /schedule-runs/{id}/result` 응답 초안을 추가했습니다.
- 최종 검토로 `current_attempt_no`는 worker 기술 재시도, `recalculation_count`는 관리자 재계산 라운드로 분리했습니다.
- 1차 tenant UX는 조직 1개 관리이고 organization switcher는 만들지 않습니다.
- publication은 같은 조직의 active 기간이 일부라도 겹치면 막습니다.
- 1차 릴리즈의 권장 직원 수와 성능 보장 기준은 2-50명입니다. 100명/31일 안정 성능 최적화는 후속 hardening 범위입니다.

## 주의 사항

- 현재 작업 폴더는 Git 저장소가 아니므로 superpowers의 commit 단계는 수행하지 못했습니다.
- 사용자가 Git 초기화를 요청하면 이후 문서 변경분을 commit할 수 있습니다.
