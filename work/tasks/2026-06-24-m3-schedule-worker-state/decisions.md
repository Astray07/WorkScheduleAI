# M3 Schedule Worker State Decisions

## 1. Redis 없이 in-process worker 먼저

1차 로컬/테스트 흐름에서는 Redis 없이 동기 실행합니다. 함수 경계를 worker 모듈로 분리해 Railway worker service에서 같은 함수를 호출할 수 있게 둡니다.

## 2. create API 외부 계약 유지

API는 내부적으로 `queued` run을 만든 뒤 즉시 execute하여 기존 `202 succeeded` 응답 계약을 유지합니다. 프론트엔드 polling 상태는 별도 queued fixture와 직접 상태 조회로 구현할 수 있습니다.

## 3. cancel API 추가

M0 OpenAPI에는 cancel path가 없지만, 1차 UI acceptance criteria가 queued/running cancel 버튼을 요구하므로 `POST /cancel` endpoint를 추가합니다.
