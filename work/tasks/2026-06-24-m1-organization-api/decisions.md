# Decisions

## 1. 인증 제외

M0 OpenAPI에는 signed-in admin 전제가 있지만 아직 인증 모델이 없습니다. 이번 단계는 DB persistence와 response contract를 먼저 검증하고, membership 자동 생성은 인증 구현 후 연결합니다.

## 2. Sync DB session

현재 SQLAlchemy 모델과 테스트 기반은 sync session입니다. FastAPI에서 sync route/dependency를 사용해 event loop blocking을 피하고, async SQLAlchemy 전환은 실제 PostgreSQL 연결 전략을 정할 때 검토합니다.

## 3. ID 생성

OpenAPI fixture와 계약의 prefixed opaque id를 유지하기 위해 `org_`, `role_` prefix와 uuid4 hex를 사용합니다.

