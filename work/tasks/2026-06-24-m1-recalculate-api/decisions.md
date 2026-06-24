# Decisions

## 2026-06-24

- 재계산 요청은 `ScheduleRecalculationRequest`로 별도 기록합니다. `ScheduleRun.idempotency_key`는 생성 요청용이므로 재계산 idempotency와 섞지 않습니다.
- 재계산은 `recalculation_count`만 증가시키고 `current_attempt_no`는 유지합니다. worker 기술 재시도와 관리자 재계산 라운드의 의미를 분리하기 위해서입니다.
- 재계산 4회차는 409로 막습니다. `manual_review_required` issue 저장은 실제 issue 테이블이 생긴 뒤 구현합니다.
- mock result는 승인+재계산 상태에서 미배정 issue를 제거합니다. 이는 P0의 “완화안 승인 → 재계산” 흐름을 UI가 확인할 수 있게 하기 위한 계약입니다.
