# Brief

## 목표

M1 도메인/테넌시의 첫 DB 기반을 만듭니다. 조직, 사용자, 멤버십, 직원, 역할, 직원-역할, 조합 제한의 SQLAlchemy 모델과 핵심 constraint를 추가해 이후 CRUD/API/migration 작업의 기준을 세웁니다.

## 비목표

- 실제 PostgreSQL 연결과 Alembic migration 파일 생성은 하지 않습니다.
- FastAPI CRUD route는 구현하지 않습니다.
- RLS 정책 SQL은 구현하지 않습니다.
- 근무 유형, 휴가, ScheduleRun 결과 테이블은 이번 단계에서 만들지 않습니다.

## 성공 기준

- SQLAlchemy 2.0 declarative model이 추가됩니다.
- tenant 하위 데이터가 `organization_id`를 갖습니다.
- `employees(organization_id, employee_code)` unique가 테스트됩니다.
- `roles(organization_id, name)` unique가 테스트됩니다.
- `employee_roles(organization_id, employee_id, role_id)` unique가 테스트됩니다.
- `pair_constraints`의 정규화와 역순 중복 방지가 테스트됩니다.
- 모든 테스트가 통과합니다.

## 제약

- TDD 순서를 지킵니다.
- PostgreSQL 대상 설계 원칙은 유지하되, 이번 검증은 로컬 SQLite in-memory로 제한합니다.
- API 공개 id와 fixture의 `org_`, `emp_`, `role_` 형태를 고려해 모델 id는 문자열로 둡니다.

