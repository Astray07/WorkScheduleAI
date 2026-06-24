# M1 Publication Excel API Handoff

## 현재 상태

재계산된 mock ScheduleRun을 publication으로 발행하고 `.xlsx`로 다운로드하는 API 구현, 전체 검증, 커밋을 완료했습니다.

## 구현 내용

- `SchedulePublication` SQLAlchemy 모델을 추가했습니다.
- Alembic revision `20260624_0006`으로 `schedule_publications` 테이블을 추가했습니다.
- result API에 `assignment_snapshot_hash`, `issue_snapshot_hash`, publication payload, `read_only` 반영을 추가했습니다.
- `POST /organizations/{organization_id}/schedule-runs/{schedule_run_id}/publications`를 추가했습니다.
- `GET /organizations/{organization_id}/schedule-publications/{publication_id}/excel`을 추가했습니다.
- 엑셀 파일은 표준 라이브러리로 최소 `.xlsx` 패키지를 생성합니다.

## 다음 단계

1. 다음 범위로 실제 SchedulePublication archive 또는 frontend 결과 화면 연결을 선택합니다.
