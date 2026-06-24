# Decisions

## 1. 이번 단계 범위

M1 전체 CRUD가 아니라 DB foundation만 구현합니다. 현재 필요한 것은 API와 migration 작업이 의존할 tenant-aware schema의 최소 골격입니다.

## 2. ID 타입

모델의 `id`는 문자열로 둡니다. M0 OpenAPI와 fixture가 `org_`, `emp_`, `role_` 같은 opaque prefixed id를 사용하고 있으므로, 첫 구현에서는 API 계약과 DB 모델을 맞춥니다.

## 3. SQLite 테스트

PostgreSQL 전용 RLS와 exclusion constraint는 이번 단계에서 테스트하지 않습니다. 대신 SQLite in-memory로 일반 FK, unique, check constraint, pair normalization helper를 검증합니다.

## 4. PairConstraint 정규화 위치

DB check constraint만으로 역순 입력을 보정하지 않습니다. 애플리케이션 생성 helper가 employee id를 정렬하고, DB unique constraint가 중복을 막습니다.

