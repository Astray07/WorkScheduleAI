# Release Feedback Hardening Decisions

## 1. P0/P1 API 동작부터 수정

RLS와 Redis worker는 별도 큰 작업입니다. 이번 턴에서는 발행 불변성, override 범위, proposal 원인, manual validation, snapshot 재현성처럼 API 동작으로 바로 검증 가능한 릴리즈 차단 항목을 먼저 닫습니다.

## 2. OverrideApproval 스키마 확장 대신 proposal id 파싱

기존 DB migration을 크게 늘리지 않기 위해 이번 단계에서는 proposal id와 affected slot id로 승인 범위를 계산합니다. 추후 정규화가 필요하면 OverrideApproval에 scope JSON 또는 explicit slot/employee FK를 추가할 수 있습니다.

## 3. 수동 수정은 저장하지 않고 validate만 구현

계약의 endpoint는 validate입니다. 1차 릴리즈 기준의 “수동 수정 후 서버 검증”을 충족하기 위해 저장 API 없이 validation response만 제공합니다.

## 4. RLS는 PostgreSQL 전용 migration으로 추가

현재 테스트와 로컬 개발 DB는 SQLite입니다. RLS는 PostgreSQL 기능이므로 Alembic revision은 SQLite에서 no-op으로 두고, PostgreSQL일 때 tenant child table에 `ENABLE/FORCE ROW LEVEL SECURITY`와 `tenant_isolation` policy를 적용합니다. API 요청은 path의 `organization_id`를 `SET LOCAL app.current_organization_id`로 설정합니다.
