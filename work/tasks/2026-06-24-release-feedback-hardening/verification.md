# Release Feedback Hardening Verification

## RED 확인

- `python -m pytest tests\api\test_schedule_runs_api.py -q`
- 결과: 6 failed, 23 passed
- 실패 지점:
  - 발행된 ScheduleRun 재계산이 `202`로 허용됨
  - 승인된 휴가 override가 run 전체에 적용됨
  - 역할 부족 미배정에도 `approve_time_off_override` proposal 생성
  - manual edit validation endpoint `404`
  - snapshot payload에 `generated_shift_slots` 누락

## GREEN / 회귀 검증

- `python -m pytest tests\db\test_alembic_migrations.py tests\api\test_schedule_runs_api.py tests\api\test_p0_vertical_slice_api.py -q`: 41 passed
- `python -m pytest -q`: 107 passed
- `cd frontend; npm run build`: 성공
- `git diff --check`: 통과

## 확인한 성공 기준

- 발행된 ScheduleRun 재계산은 `409 SCHEDULE_RUN_ALREADY_PUBLISHED`로 차단됩니다.
- 휴가 override proposal은 employee/slot 범위를 포함하고, 승인된 slot만 solver unavailable에서 제외됩니다.
- 역할 자격 부족처럼 휴가 후보가 없는 미배정은 `mark_manual_review` proposal을 반환합니다.
- manual edit validation endpoint가 자격 불일치와 발행 잠금을 검증합니다.
- ScheduleInputSnapshot payload에 `generated_shift_slots`, `generated_schedule_requirements`가 포함됩니다.
- PostgreSQL 전용 RLS migration이 추가됐고, API DB dependency가 path `organization_id`를 `app.current_organization_id`로 설정합니다.

## 남은 위험

- RLS는 SQLite 테스트 환경에서는 SQL 실행이 no-op입니다. 실제 PostgreSQL 인스턴스에서 migration 적용과 tenant 격리 쿼리 검증이 추가로 필요합니다.
- Redis queue 분리, 고급 assumption literal 진단, 수동 편집 저장 API/UI는 이번 범위 밖입니다.
