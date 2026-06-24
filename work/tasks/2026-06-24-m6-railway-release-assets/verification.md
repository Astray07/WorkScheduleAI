# M6 Railway Release Assets Verification

## 공식 문서 확인

확인일: 2026-06-24

- Railway config-as-code reference: `railway.json`/`railway.toml`, `startCommand`, `preDeployCommand`, `healthcheckPath`
- Railway FastAPI guide: GitHub/CLI/Dockerfile 배포
- Railway cron/workers/queues guide: API service와 background worker service 분리, Redis queue 구성
- FastAPI Docker guide: Python base image 기반 Docker build

## TDD 실패 확인

명령:

```powershell
python -m pytest tests\scripts\test_seed_demo.py -q
```

결과:

- 예상 실패: `ModuleNotFoundError: No module named 'scripts.seed_demo'`

## Focused Tests

명령:

```powershell
python -m pytest tests\scripts\test_seed_demo.py -q
python -m pytest tests\api\test_api_smoke.py -q
```

결과:

- `2 passed`
- `3 passed`

## Migration And Seed Smoke

명령:

```powershell
$env:DATABASE_URL='sqlite:///work/tasks/2026-06-24-m6-railway-release-assets/railway-smoke.sqlite3'
python -m alembic upgrade head
python -m scripts.seed_demo
```

결과:

- Alembic head까지 적용 성공
- seed output:

```json
{"employee_count": 4, "organization_id": "org_demo_p0", "publication_id": "publication_demo_p0", "schedule_run_id": "run_demo_p0_recalculated", "status": "seeded"}
```

## Full Verification

명령:

```powershell
python -m pytest -q
cd frontend
npm run build
git diff --check
```

결과:

- `97 passed in 4.14s`
- frontend TypeScript/Vite build 통과
- `git diff --check` exit 0
- 줄바꿈 경고: 일부 파일이 다음 Git touch 시 CRLF로 바뀔 수 있다는 경고만 표시됨

## Docker Build

명령:

```powershell
docker build -t workscheduleai-api:railway-smoke .
```

결과:

- 실행하지 못함: Docker CLI는 있으나 Docker Desktop Linux engine daemon이 실행 중이 아니어서 `failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine` 발생

남은 위험:

- 실제 Railway 또는 Docker daemon이 켜진 환경에서 image build를 한 번 더 확인해야 합니다.

## 커밋

- `feat: add railway release assets`
