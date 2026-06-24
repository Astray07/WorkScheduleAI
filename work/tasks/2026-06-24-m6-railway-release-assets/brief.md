# M6 Railway Release Assets Brief

## 목표

Railway 배포에 필요한 API Dockerfile/config, 환경 변수 문서, demo seed를 추가합니다.

## 비목표

- 실제 Railway 프로젝트를 생성하거나 배포하지 않습니다.
- Redis 기반 비동기 worker queue를 완성하지 않습니다.
- 결제, 인증, 운영 모니터링을 구현하지 않습니다.

## 성공 기준

- Railway API service가 Dockerfile과 `railway.json`으로 빌드/시작/헬스체크 구성을 가집니다.
- Alembic이 `DATABASE_URL` 환경 변수를 사용해 배포 DB에 migration을 적용할 수 있습니다.
- P0 demo seed가 idempotent하게 조직, 직원 4명, 휴가 1건, 상극 조합 1건, 승인/재계산된 ScheduleRun, SchedulePublication을 생성합니다.
- Railway 배포 문서에 API, frontend, worker, PostgreSQL, Redis, 환경 변수, migration, seed 절차가 정리됩니다.

## 제약

- 공식 Railway 문서 확인일은 2026-06-24입니다.
- 배포 산출물은 현재 1차 릴리즈 구조에 맞춰 단순하게 유지합니다.
