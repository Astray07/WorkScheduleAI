# Release Feedback Remediation Decisions

## 1. 영속 artifact부터 고정

Redis queue, RLS, 고급 완화안까지 한 번에 구현하면 범위가 너무 커집니다. 먼저 ScheduleRun이 생성한 결과를 DB에 저장하고, publication은 해당 저장본의 JSON snapshot을 보존하도록 고정합니다.

## 2. worker callback 방식

기존 `schedule_worker.py`가 API route를 import하면 순환 import가 생깁니다. worker는 상태 전이를 담당하고, route/service 쪽에서 solver executor callback을 넘겨 artifact를 생성/저장합니다.

## 3. mock fallback은 legacy 경로로만 유지

shift template이 없는 기존 테스트/데모 호환을 위해 mock fallback은 남기되, 프론트 P0와 seed는 shift template을 생성해 solver path를 사용하도록 수정합니다.

## 4. publication snapshot은 JSON으로 먼저 고정

정규화된 publication assignment table까지 확장하면 변경 범위가 커집니다. 이번 단계에서는 ScheduleRun artifact row를 저장하고, 발행 시 API 응답 payload와 같은 형태의 JSON snapshot을 보존해 확정본 불변성을 먼저 보장합니다.

## 5. P0 완화 흐름은 단일 부사수 휴가로 검증

프론트와 P0 테스트 모두 E002만 `부사수` 역할을 갖게 해서 7월 1일 휴가로 실제 `unfilled_requirement`가 발생하도록 했습니다. 승인 후 재계산에서는 휴가 override를 반영해 14개 배정이 완성되는 흐름을 검증합니다.
