# Release Feedback Remediation Brief

## 목표

1차 릴리즈 리뷰에서 지적된 P0/P1 차단 항목 중 실제 릴리즈 신뢰성에 직접 영향을 주는 부분을 수정합니다.

## 우선 범위

- 프론트 P0 흐름이 shift template을 만들고 solver path를 타도록 수정합니다.
- ScheduleRun worker 실행 시 solver 결과를 생성하고 저장합니다.
- ScheduleRun 결과 조회와 Excel 다운로드가 저장된 결과 또는 publication snapshot을 사용합니다.
- ScheduleInputSnapshot에 shift template, requirement, unavailability, pair constraint 입력을 포함합니다.
- 같은 idempotency key가 다른 snapshot으로 재사용되면 `409 Conflict`를 반환합니다.
- Railway deploy dependency에 PostgreSQL driver를 추가합니다.

## 비범위

- Redis queue worker 완성
- PostgreSQL RLS 정책 전체 구현
- 고급 정책 objective 전체 구현
- 수동 편집 UI/API 전체 구현

## 성공 기준

- P0 프론트 데모가 shift template 생성 API를 호출합니다.
- ScheduleRun 생성 응답의 `solver_status`가 solver 결과를 반영합니다.
- 결과 artifact가 DB에 저장되고 GET 시 재계산하지 않습니다.
- publication 이후 직원명 등 기준 정보가 바뀌어도 Excel 다운로드 결과가 변하지 않습니다.
- idempotency conflict 테스트가 통과합니다.
- 전체 pytest와 frontend build가 통과합니다.
