# M6 Railway Release Assets Decisions

## 1. Dockerfile 기반 API service

Railway가 Dockerfile을 자동 감지하고 config-as-code에서 `DOCKERFILE` builder를 지정할 수 있으므로 API service는 root Dockerfile로 배포합니다.

## 2. Frontend는 별도 Railway service

프론트엔드는 `frontend/` root directory의 별도 service로 배포하는 문서화 방식을 사용합니다. `VITE_API_BASE_URL`로 API URL을 주입합니다.

## 3. Worker는 1차에서 문서화된 별도 service

현재 ScheduleRun은 in-process 실행 경로가 있으므로 Redis queue worker 완성은 후속 hardening입니다. 다만 Railway 구성 문서에는 worker service와 Redis 연결 방향을 명시합니다.

## 4. Seed는 직접 DB idempotent upsert

배포 직후 데모 데이터를 만들 수 있도록 API 호출 대신 SQLAlchemy session으로 안정적인 id를 upsert합니다.
