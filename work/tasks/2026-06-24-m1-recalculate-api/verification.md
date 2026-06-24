# Verification

## RED

- `python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py tests/api/test_schedule_runs_api.py -q`
- 결과: collection error 2건
- 실패 사유: `ScheduleRecalculationRequest` 모델이 아직 없어 domain/API 테스트 import가 실패했습니다.

## 중간 RED

- `python -m pytest tests/api/test_schedule_runs_api.py -q`
- 결과: 5 failed, 9 passed
- 실패 사유: recalculate endpoint가 없어 404가 발생했고, result의 `recalculation_count`가 아직 0으로 남았습니다.

## DB GREEN

- `python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py -q`
- 결과: `23 passed in 1.20s`

## API GREEN

- `python -m pytest tests/api/test_schedule_runs_api.py -q`
- 결과: `14 passed in 0.90s`

## 집중 회귀

- `python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py tests/api/test_schedule_runs_api.py -q`
- 결과: `37 passed in 1.87s`

## 전체 회귀

- `python -m pytest -q`
- 결과: `60 passed in 2.80s`

## Diff 검사

- `git diff --check`
- 결과: exit 0
- 참고: 여러 파일에 대해 Git CRLF 변환 경고가 출력되었지만 whitespace error는 없었습니다.
