# Verification

## RED

- `python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py tests/api/test_schedule_runs_api.py -q`
- 결과: collection error 2건
- 실패 사유: `ScheduleRun`, `ScheduleInputSnapshot` 모델이 아직 없어 domain/API 테스트 import가 실패했습니다.

## 중간 RED

- `python -m pytest tests/api/test_schedule_runs_api.py -q`
- 결과: 5 failed
- 실패 사유: `POST /organizations/org_1/schedule-runs` 라우트가 아직 없어 404로 실패했습니다.

## DB GREEN

- `python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py -q`
- 결과: `19 passed in 0.82s`

## API GREEN

- `python -m pytest tests/api/test_schedule_runs_api.py -q`
- 결과: `5 passed in 0.55s`

## 집중 회귀

- `python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py tests/api/test_schedule_runs_api.py -q`
- 결과: `24 passed in 1.26s`

## 전체 회귀

- `python -m pytest -q`
- 결과: `47 passed in 1.55s`

## Diff 검사

- `git diff --check`
- 결과: exit 0
- 참고: 여러 파일에 대해 Git CRLF 변환 경고가 출력되었지만 whitespace error는 없었습니다.
