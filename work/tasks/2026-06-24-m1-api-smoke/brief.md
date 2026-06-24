# Brief

## 목표

FastAPI 앱의 최소 진입점을 추가합니다. DB, worker, solver 없이 `/health`와 M0 계약 요약 API만 제공해 이후 API route 구현의 기준을 만듭니다.

## 비목표

- 인증, 조직 CRUD, DB 연결은 구현하지 않습니다.
- OpenAPI M0 전체를 FastAPI route로 구현하지 않습니다.
- worker queue나 OR-Tools는 다루지 않습니다.

## 성공 기준

- `create_app()`이 FastAPI 앱을 반환합니다.
- `GET /health`가 `{"status": "ok"}`를 반환합니다.
- `GET /contracts/m0/summary`가 M0 path/schema 누락 없음과 fixture 목록을 반환합니다.
- 테스트를 먼저 작성하고 RED 실패를 확인한 뒤 GREEN 통과합니다.

## 제약

- 기존 M0 계약 파일은 수정하지 않습니다.
- FastAPI endpoint는 async로 작성합니다.
- 계약 요약 endpoint는 내부 개발용 smoke endpoint이며 운영 기능으로 일반화하지 않습니다.

