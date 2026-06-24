# Decisions

## 1. Endpoint 범위

이번 단계에서는 `/health`와 `/contracts/m0/summary`만 추가합니다. P0 vertical slice의 실제 업무 route는 DB와 domain model이 필요하므로 후속 단계로 둡니다.

## 2. Contract summary

`/contracts/m0/summary`는 frontend mock, CI smoke, 개발자 확인용입니다. M0 OpenAPI 자체를 대체하지 않습니다.

## 3. Async route

FastAPI 지침에 따라 I/O가 작더라도 route handler는 async로 작성합니다. 현재는 로컬 JSON 파일만 읽으므로 복잡한 async file I/O는 도입하지 않습니다.

