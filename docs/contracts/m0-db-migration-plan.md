# M0 DB Migration Plan

## 목적

이 문서는 실제 Alembic migration을 작성하기 전, WorkScheduleAI M0에서 고정할 DB 구조와 invariant를 정의합니다. 저장소에는 아직 애플리케이션 스캐폴딩이 없으므로 migration 파일은 만들지 않습니다.

## Migration 순서

1. 공통 enum type을 만듭니다.
   - schedule_run_status
   - solution_quality
   - issue_type
   - issue_severity
   - proposal_type
   - proposal_status
   - assignment_source
   - publication_status
2. tenant root 테이블을 만듭니다.
   - organizations
   - users
   - memberships
3. 기준 정보 테이블을 만듭니다.
   - employees
   - roles
   - employee_roles
   - shift_types
   - shift_requirements
   - unavailabilities
   - pair_constraints
   - schedule_policies
   - schedule_policy_role_weights
4. 실행 입력과 실행 기록 테이블을 만듭니다.
   - schedule_input_snapshots
   - schedule_runs
5. 결과와 진단 테이블을 만듭니다.
   - shift_slots
   - assignments
   - schedule_issues
   - solver_diagnostic_events
   - relaxation_proposals
   - override_approvals
6. 확정본 테이블을 만듭니다.
   - schedule_publications
7. RLS 정책과 `FORCE ROW LEVEL SECURITY`를 적용합니다.

## 핵심 Invariant

- `organizations.name`은 전역 unique가 아닙니다.
- `employees(organization_id, employee_code)`는 unique입니다.
- `roles(organization_id, name)`은 unique입니다.
- `shift_types(organization_id, name)`은 unique입니다.
- `pair_constraints`는 `(organization_id, normalized_employee_a_id, normalized_employee_b_id, type)` unique입니다.
- `pair_constraints`는 `normalized_employee_a_id < normalized_employee_b_id` check constraint를 둡니다.
- `assignments(schedule_run_id, shift_slot_id, role_id, employee_id)`는 unique입니다.
- `assignments(schedule_run_id, shift_slot_id, employee_id)`도 unique입니다. 1차 릴리즈에서는 한 직원이 같은 슬롯에서 여러 역할을 동시에 맡지 않습니다.
- 같은 슬롯/역할의 필요 인원 수를 넘는 assignment는 application validation과 solver output validation으로 막습니다.
- `schedule_publications`는 같은 조직에서 active 기간이 겹치면 저장을 막습니다.
- 자식 테이블의 `organization_id`는 복합 FK 또는 trigger로 부모와 일치하도록 강제합니다.

## PairConstraint 정규화

쓰기 시점에 employee id를 정렬해 작은 값이 `normalized_employee_a_id`, 큰 값이 `normalized_employee_b_id`가 되도록 합니다. 자기 자신 조합은 check constraint와 application validation에서 모두 거부합니다.

## Publication overlap 처리

PostgreSQL에서는 `daterange(period_start, period_end, '[)')`와 GiST exclusion constraint를 우선 고려합니다.

권장 constraint:

```sql
EXCLUDE USING gist (
  organization_id WITH =,
  daterange(period_start, period_end, '[)') WITH &&
)
WHERE (status = 'published');
```

이 constraint를 쓰려면 `btree_gist` extension이 필요합니다. Railway PostgreSQL에서 extension 사용 가능 여부를 확인한 뒤 적용합니다. extension 사용이 어렵다면 transaction 안에서 `SELECT ... FOR UPDATE` 기반 overlap validation과 partial index를 함께 사용합니다.

## RLS 계획

- tenant 데이터가 있는 모든 주요 테이블에는 `organization_id`를 저장합니다.
- 각 DB transaction 시작 시 `SET LOCAL app.current_organization_id = '<uuid>'`를 설정합니다.
- RLS predicate는 `organization_id = current_setting('app.current_organization_id')::uuid` 형태를 기본으로 합니다.
- 각 tenant 테이블에는 `ALTER TABLE ... ENABLE ROW LEVEL SECURITY`와 `ALTER TABLE ... FORCE ROW LEVEL SECURITY`를 적용합니다.
- connection pool과 PgBouncer transaction pooling을 고려해 session 변수 지속성에 의존하지 않습니다.

## M0에서 실제 migration을 만들지 않는 이유

아직 FastAPI/SQLAlchemy/Alembic 스캐폴딩이 없습니다. M0에서는 계약을 고정하고, M1에서 프로젝트 스캐폴딩과 함께 migration 파일 및 DB 테스트를 작성합니다.

