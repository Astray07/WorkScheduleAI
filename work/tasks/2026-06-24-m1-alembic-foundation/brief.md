# Brief

## 목표

M1 도메인 DB 모델을 Alembic migration 경로로 연결합니다. 첫 migration으로 tenant/domain foundation 테이블을 생성하고, 로컬 테스트에서 Alembic upgrade가 실제 테이블과 핵심 constraint를 만드는지 확인합니다.

## 비목표

- 운영 PostgreSQL 데이터베이스에 연결하지 않습니다.
- PostgreSQL RLS policy를 실제로 적용하지 않습니다.
- ScheduleRun, publication, solver 결과 테이블 migration은 이번 단계에서 만들지 않습니다.
- API CRUD route는 구현하지 않습니다.

## 성공 기준

- `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, 첫 revision 파일이 추가됩니다.
- Alembic env가 `work_schedule_ai.db.models.Base.metadata`를 target metadata로 사용합니다.
- 테스트가 SQLite 임시 DB에 Alembic upgrade를 실행하고, M1 foundation 테이블 생성을 검증합니다.
- 테스트가 migration으로 생성된 핵심 unique/check constraint 이름을 검증합니다.
- 전체 테스트가 통과합니다.

## 제약

- TDD 순서를 지킵니다.
- PostgreSQL 전용 RLS는 문서와 TODO marker로 남기고, 실제 적용은 PostgreSQL integration 단계로 미룹니다.
- migration 파일은 현재 SQLAlchemy 모델과 일치해야 합니다.

