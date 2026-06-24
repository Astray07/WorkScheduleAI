# M1 Publication Excel API Brief

## 목표

P0 mock vertical slice의 마지막 계약인 `SchedulePublication` 생성과 엑셀 다운로드 API를 구현합니다.

## 비목표

- 실제 OR-Tools 결과 저장 구조를 만들지 않습니다.
- 엑셀 업로드는 구현하지 않습니다.
- 고급 서식, 다중 시트, 사용자별 다운로드 권한은 구현하지 않습니다.
- LLM 설명 호출을 추가하지 않습니다.

## 성공 기준

- 재계산 후 issue가 없는 mock ScheduleRun을 publication으로 발행할 수 있습니다.
- 발행 후 result API는 `read_only: true`와 publication payload를 반환합니다.
- 같은 조직의 active publication 기간이 겹치면 새 publication을 막습니다.
- publication ID로 `.xlsx` 응답을 다운로드할 수 있습니다.
- 전체 테스트가 통과합니다.

## 제약

- ScheduleRun 실행 기록과 SchedulePublication 확정본은 분리합니다.
- snapshot hash mismatch는 stale UI로 간주하고 409를 반환합니다.
- 1차 릴리즈 기준인 최대 생성 기간 31일 범위 안에서만 다룹니다.
- OpenAI API key는 사용하지 않습니다.
