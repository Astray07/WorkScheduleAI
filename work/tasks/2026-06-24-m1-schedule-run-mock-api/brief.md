# Brief

## 목표

P0 vertical slice의 1주 근무표 생성 단계에 필요한 ScheduleRun 생성/조회/result mock API를 구현합니다.

## 비목표

- OR-Tools solver 통합
- 완화안 승인 API
- 재계산 API
- SchedulePublication 확정본 생성
- 엑셀 다운로드

## 성공 기준

- `POST /organizations/{organization_id}/schedule-runs`가 ScheduleRun과 ScheduleInputSnapshot을 저장하고 202를 반환합니다.
- `GET /schedule-runs/{schedule_run_id}`가 상태 polling 응답 계약을 반환합니다.
- `GET /schedule-runs/{schedule_run_id}/result`가 1주 grid mock 결과, 미배정 ScheduleIssue, suggested RelaxationProposal을 반환합니다.
- `current_attempt_no`는 1, `recalculation_count`는 0으로 시작합니다.
- 생성 기간은 1-31일로 제한합니다.
- 결과의 LLM 설명은 외부 호출 없이 `server_template` fallback만 사용합니다.
- ScheduleRun 실행 기록과 SchedulePublication 확정본은 분리하며, 이번 작업에서는 publication을 생성하지 않습니다.

## 제약과 가정

- 이번 mock API는 UI/API 병렬 개발을 위한 계약 고정입니다. 실제 근무표 생성은 후속 OR-Tools 통합에서 구현합니다.
- 기간 길이는 `period_start`와 `period_end`를 포함해 계산합니다. `2026-07-01`부터 `2026-07-07`까지는 7일입니다.
- 미배정은 hard 제약 실패가 아니라 soft penalty `ScheduleIssue`로 표현합니다.
- LLM에는 어떤 데이터도 보내지 않습니다.
