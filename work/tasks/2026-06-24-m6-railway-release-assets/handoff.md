# M6 Railway Release Assets Handoff

## 현재 상태

Railway 배포 산출물과 P0 demo seed를 추가하고 커밋했습니다.

## 완료한 내용

- root API `Dockerfile`, `.dockerignore`, `railway.json` 추가
- `frontend/railway.json` 추가
- `deploy` optional dependency 추가
- Alembic `DATABASE_URL` override 추가
- API `CORS_ALLOW_ORIGINS` 지원 추가
- idempotent `scripts.seed_demo` 추가
- Railway 배포 문서 작성
- seed focused tests, API smoke, 전체 tests, frontend build, migration/seed smoke 통과

## 다음 단계

1. Docker daemon 또는 Railway 환경에서 image build/deploy smoke를 확인합니다.
