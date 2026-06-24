# Operational Monitoring Notes

확인일: 2026-06-24

## 추가된 endpoint

- `GET /operations/schedule-runs/metrics`
  - `total_runs`
  - `active_runs`
  - `status_counts`
  - `completed_average_duration_seconds`
- `GET /health/ready`
  - `status`
  - `database`
  - `redis`

## 의도

API/worker/Railway 분리 이후 최소 운영 가시성을 제공합니다. 별도 metrics backend는 아직 붙이지 않고, 로컬/CI에서 검증 가능한 pull endpoint로 시작합니다.

## Smoke checklist

- API process에서 `GET /health`가 `{"status":"ok"}`를 반환합니다.
- API process에서 `GET /health/ready`가 database `ok`를 반환합니다.
- Redis 미설정 로컬 환경에서는 redis `not_configured`를 반환합니다.
- Railway 환경에서는 `REDIS_URL` 설정 후 redis `ok`를 기대합니다.
- `GET /operations/schedule-runs/metrics`에서 queued/running count가 worker backlog를 드러냅니다.

## 보류

- GitHub push, Railway/staging 배포, P0 수동 시나리오 검증은 마지막 통합 점검 단계까지 미룹니다.
- metrics backend, alert rule, dashboard는 후속 운영 고도화 범위입니다.
