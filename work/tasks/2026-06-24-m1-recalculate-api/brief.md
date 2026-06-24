# Brief

## 목표

P0 vertical slice의 완화안 승인 이후 재계산 단계를 구현합니다.

## 비목표

- 실제 OR-Tools solver 재실행
- worker queue
- manual assignment lock
- SchedulePublication 확정본
- Excel 다운로드

## 성공 기준

- 승인된 OverrideApproval이 있을 때만 재계산을 허용합니다.
- 재계산은 `recalculation_count`만 증가시키고 `current_attempt_no`는 변경하지 않습니다.
- `recalculation_count`는 최대 3회로 제한합니다.
- 동일 `Idempotency-Key` 재호출은 중복 증가시키지 않습니다.
- mock result는 재계산 후 미배정 issue를 제거하고 모든 14개 requirement를 배정합니다.
- 기존 전체 테스트가 계속 통과합니다.

## 제약과 가정

- 이번 단계는 mock 재계산입니다. OR-Tools 통합 전까지 solver 결과는 deterministic template로 유지합니다.
- approved override가 다음 solver 실행의 고정 제약이 된다는 계약을 API 레벨에서 먼저 고정합니다.
- 재계산 limit 초과 시 이번 단계에서는 409를 반환합니다. `manual_review_required` ScheduleIssue 저장은 실제 issue 테이블 도입 후 보강합니다.
