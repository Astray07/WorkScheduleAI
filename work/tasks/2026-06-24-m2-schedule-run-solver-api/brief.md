# M2 ScheduleRun Solver API Brief

## 목표

ShiftType/ShiftRequirement가 있는 조직의 ScheduleRun result를 OR-Tools solver 기반으로 생성합니다.

## 비목표

- 기존 no-template P0 mock 계약을 제거하지 않습니다.
- Assignment/ScheduleIssue 영속 테이블을 추가하지 않습니다.
- 승인된 완화안이 solver input을 바꾸는 재계산 고도화는 이번 작업에서 하지 않습니다.
- worker 비동기 큐를 추가하지 않습니다.

## 성공 기준

- shift template이 있으면 result slots/requirements/assignments가 해당 템플릿에서 생성됩니다.
- 채울 수 없는 required role은 `unfilled_requirement` ScheduleIssue로 표시됩니다.
- 기존 P0 mock API 테스트가 계속 통과합니다.
- 전체 테스트가 통과합니다.

## 제약

- OR-Tools가 solver-backed path의 근무표를 생성합니다.
- LLM은 사용하지 않습니다.
- 개인정보를 외부로 보내지 않습니다.
