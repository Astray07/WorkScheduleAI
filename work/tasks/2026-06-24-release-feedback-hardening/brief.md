# Release Feedback Hardening Brief

## 목표

2차 리뷰에서 지적된 1차 릴리즈 차단/신뢰도 항목을 좁은 범위로 수정합니다.

## 우선 범위

- 발행된 ScheduleRun은 재계산으로 artifact를 수정할 수 없게 막습니다.
- 휴가 override 승인은 전체 run이 아니라 proposal이 가리키는 slot/employee 인스턴스에만 적용합니다.
- 완화안은 실제 원인 후보가 있을 때만 `approve_time_off_override`를 제안하고, 원인이 역할 자격 부족이면 수동 검토 제안으로 둡니다.
- 계약에 있는 manual edit validation API를 최소 구현합니다.
- ScheduleInputSnapshot에 생성될 shift slot과 per-run requirement 목록을 포함합니다.
- PostgreSQL RLS migration과 request tenant context hook을 추가합니다.

## 비범위

- Redis queue 분리
- 고급 assumption literal 진단 모델 전체
- 수동 편집 저장 API/UI
- 실제 PostgreSQL 인스턴스에서의 RLS end-to-end 검증

## 성공 기준

- published run 재계산 요청은 `409 SCHEDULE_RUN_ALREADY_PUBLISHED`입니다.
- 하나의 휴가 override 승인 후 재계산해도 같은 직원의 다른 휴가 slot은 계속 미배정으로 남습니다.
- 역할 자격 부족으로 생긴 미배정은 휴가 override proposal을 만들지 않습니다.
- manual edit validation endpoint가 자격/휴가/상극/발행 잠금을 검증합니다.
- snapshot payload에 `generated_shift_slots`, `generated_schedule_requirements`가 포함됩니다.
- PostgreSQL용 RLS 정책 migration이 추가되고, organization path 요청은 `app.current_organization_id`를 설정합니다.
- 전체 pytest와 frontend build가 통과합니다.
