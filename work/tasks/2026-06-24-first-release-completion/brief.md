# First Release Completion Brief

## 목표

WorkScheduleAI 1차 릴리즈를 “완료 후보”로 닫기 위해 마지막 필수 방어선과 품질 게이트를 구현합니다.

## 우선 범위

- GitHub Actions CI를 추가해 backend pytest, alembic migration, frontend build를 자동 검증합니다.
- PostgreSQL RLS를 실제 PostgreSQL 데이터베이스에서 검증할 수 있는 integration test를 추가합니다.
- SolverDiagnosticEvent 테이블/마이그레이션/저장을 추가해 실패 시 조치 가능한 진단 기록을 남깁니다.
- 릴리즈 체크리스트와 남은 후속 범위를 문서화합니다.

## 비범위

- Redis queue worker 완전 구현
- 고급 assumption literal CP-SAT 진단 모델 전체
- 수동 편집 저장 UI/API
- 직원 100명/31일 성능 hardening

## 성공 기준

- 로컬 기본 `python -m pytest -q`가 통과합니다.
- `frontend`의 `npm run build`가 통과합니다.
- CI workflow가 동일 검증과 PostgreSQL RLS integration test를 실행하도록 구성됩니다.
- `SolverDiagnosticEvent`가 solver issue/proposal 원인을 DB에 저장합니다.
- 릴리즈 체크리스트에 1차 완료 범위와 후속 범위가 명확히 남습니다.
