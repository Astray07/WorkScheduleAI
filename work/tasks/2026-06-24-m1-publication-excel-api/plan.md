# M1 Publication Excel API Plan

- [x] 범위와 성공 기준을 정리합니다.
- [x] publication/excel API 실패 테스트를 먼저 작성합니다.
- [x] SchedulePublication 모델과 Alembic migration을 추가합니다.
- [x] publication 생성 API와 result read-only 반영을 구현합니다.
- [x] `.xlsx` 다운로드 응답을 구현합니다.
- [x] 전체 테스트와 `git diff --check`를 실행합니다.
- [x] 변경을 커밋합니다.

## 검증 방법

- `python -m pytest tests/api/test_schedule_runs_api.py -q`
- `python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py -q`
- `python -m pytest -q`
- `git diff --check`
