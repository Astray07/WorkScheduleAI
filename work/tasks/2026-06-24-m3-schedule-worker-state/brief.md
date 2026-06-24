# M3 Schedule Worker State Brief

## 목표

ScheduleRun worker 상태 전이, cancel, 기술 재시도 카운터를 구현합니다.

## 비목표

- Redis 큐를 붙이지 않습니다.
- background process deployment를 구현하지 않습니다.
- Assignment/ScheduleIssue attempt cleanup 테이블은 아직 추가하지 않습니다.

## 성공 기준

- worker 함수가 `queued -> running -> succeeded`를 수행합니다.
- queued/running run을 cancel할 수 있습니다.
- canceled run은 실행되지 않습니다.
- technical retry는 `current_attempt_no`만 증가시키고 `recalculation_count`를 바꾸지 않습니다.
- 기존 API 생성 응답은 succeeded 계약을 유지합니다.
- 전체 테스트가 통과합니다.

## 제약

- `current_attempt_no`는 worker 기술 재시도용입니다.
- `recalculation_count`는 관리자 재계산 라운드용입니다.
