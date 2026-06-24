# Decisions

## 1. 테스트 DB

이번 단계의 자동 검증은 SQLite 임시 파일 DB를 사용합니다. Alembic upgrade 경로와 일반 constraint 생성을 빠르게 검증하기 위한 선택입니다.

## 2. RLS 처리

RLS는 PostgreSQL 전용 기능입니다. SQLite migration 테스트에서 실행할 수 없으므로 첫 revision에는 RLS 실행을 넣지 않고, 후속 PostgreSQL migration 단계에서 raw SQL을 추가합니다.

## 3. 첫 revision 범위

첫 revision은 현재 구현된 M1 foundation 모델만 포함합니다. ScheduleRun, SchedulePublication, ShiftSlot 같은 후속 테이블은 아직 모델도 없으므로 포함하지 않습니다.

## 4. Migration 작성 방식

autogenerate 결과를 그대로 쓰기보다 명시적인 `op.create_table` migration을 작성합니다. 초기 테이블 수가 작고 constraint 이름을 테스트로 고정하기 위해서입니다.

