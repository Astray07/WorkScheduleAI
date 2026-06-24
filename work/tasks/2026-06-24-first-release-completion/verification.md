# First Release Completion Verification

## RED 확인

- `python -m pytest tests\api\test_schedule_runs_api.py::test_solver_unfilled_issue_persists_diagnostic_events tests\db\test_domain_models.py::test_solver_diagnostic_event_persists_structured_context tests\db\test_alembic_migrations.py::test_alembic_upgrade_head_creates_m1_foundation_tables tests\db\test_alembic_migrations.py::test_alembic_upgrade_head_stamps_expected_revision -q`
- 결과: import error로 실패
- 실패 이유: `SolverDiagnosticEvent` model/table/revision이 아직 없음

## GREEN / 회귀 검증

- `python -m pytest tests\api\test_schedule_runs_api.py::test_solver_unfilled_issue_persists_diagnostic_events tests\db\test_domain_models.py::test_solver_diagnostic_event_persists_structured_context tests\db\test_alembic_migrations.py::test_alembic_upgrade_head_creates_m1_foundation_tables tests\db\test_alembic_migrations.py::test_alembic_upgrade_head_creates_schedule_result_artifact_indexes tests\db\test_alembic_migrations.py::test_alembic_upgrade_head_stamps_expected_revision -q`: 5 passed
- `python -m pytest tests\db\test_postgresql_rls_integration.py -q`: 1 skipped
  - 사유: 로컬에 `TEST_POSTGRES_URL` 미설정
- `python -m pytest tests\api\test_schedule_runs_api.py tests\db\test_domain_models.py tests\db\test_alembic_migrations.py tests\db\test_postgresql_rls_integration.py -q`: 62 passed, 1 skipped
- `python -m pytest -q`: 109 passed, 1 skipped
- `cd frontend; npm run build`: 성공
- `git diff --check`: 통과

## 최종 확인

- `python -m pytest -q`: 109 passed, 1 skipped
- `npm run build` in `frontend`: 성공
- `git diff --check`: 통과

## 확인한 성공 기준

- `SolverDiagnosticEvent` model/table/migration이 추가됐습니다.
- solver issue와 proposal 생성 시 diagnostic events가 저장됩니다.
- PostgreSQL RLS integration test가 추가됐고, CI에서는 `TEST_POSTGRES_URL`로 실행됩니다.
- GitHub Actions CI가 backend pytest, PostgreSQL service, frontend build를 실행합니다.
- 1차 릴리즈 체크리스트가 `docs/release/first-release-checklist.md`에 정리됐습니다.

## 남은 위험

- 이 로컬 환경에서는 PostgreSQL service를 띄우지 않아 RLS integration이 skip됐습니다. CI 또는 별도 PostgreSQL 환경에서 실제 실행이 필요합니다.
- Redis queue worker, 100명/31일 성능 hardening, 고급 assumption literal 진단 모델은 명시적 후속 범위입니다.
