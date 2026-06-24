# M6 Railway Release Assets Plan

- [x] 범위와 성공 기준을 정리합니다.
- [x] Railway 공식 문서 기준을 기록합니다.
- [x] demo seed idempotency 테스트를 작성합니다.
- [x] demo seed script를 구현합니다.
- [x] Dockerfile, railway config, deploy dependencies를 추가합니다.
- [x] Alembic `DATABASE_URL` override와 CORS env를 보강합니다.
- [x] Railway 배포 문서를 작성합니다.
- [x] 검증을 실행합니다.
- [x] 변경을 커밋합니다.

## 검증 방법

- `python -m pytest tests\scripts\test_seed_demo.py -q`
- `python -m pytest tests\api\test_api_smoke.py -q`
- `python -m alembic upgrade head` with temp `DATABASE_URL`
- `python -m scripts.seed_demo` with temp `DATABASE_URL`
- `python -m pytest -q`
- `npm run build` in `frontend`
- `git diff --check`
