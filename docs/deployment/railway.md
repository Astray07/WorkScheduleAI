# Railway Deployment

확인일: 2026-06-24

## 공식 문서 기준

- Railway config-as-code는 `railway.json` 또는 `railway.toml`을 코드와 함께 두고 build/deploy 설정을 정의할 수 있습니다. `startCommand`, `preDeployCommand`, `healthcheckPath`, restart policy를 설정할 수 있습니다.
  https://docs.railway.com/config-as-code/reference
- Railway FastAPI guide는 GitHub repo, CLI, Dockerfile 기반 배포를 안내하며, Dockerfile이 있으면 Railway가 Dockerfile build를 사용할 수 있습니다.
  https://docs.railway.com/guides/fastapi
- Railway worker/queue guide는 API service와 background worker service를 분리하고 Redis를 queue로 사용하는 구성을 권장합니다.
  https://docs.railway.com/guides/cron-workers-queues
- FastAPI Docker guide는 Python base image에서 dependency install 후 ASGI app을 실행하는 컨테이너 구성을 안내합니다.
  https://fastapi.tiangolo.com/deployment/docker/

## Services

### API service

Root directory: repository root

Config file: `railway.json`

Build:

```text
Dockerfile
```

Pre-deploy:

```powershell
python -m alembic upgrade head
```

Start:

```powershell
python -m uvicorn work_schedule_ai.api.app:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}
```

Healthcheck:

```text
/health
```

Required variables:

- `DATABASE_URL`: Railway PostgreSQL internal connection URL
- `CORS_ALLOW_ORIGINS`: deployed frontend origin, comma-separated for multiple origins
- `APP_ENV`: `production`

Optional variables:

- `REDIS_URL`: future async worker queue
- `LLM_PROVIDER`: future provider selector
- `LLM_API_KEY`: future provider key; not required for fallback mode

### Frontend service

Root directory: `frontend`

Config file: `frontend/railway.json`

Build:

```powershell
npm ci && npm run build
```

Start:

```powershell
npm run preview -- --host 0.0.0.0 --port ${PORT:-4173}
```

Required variables:

- `VITE_API_BASE_URL`: public API service URL

After the frontend domain is issued, set the same origin in the API service `CORS_ALLOW_ORIGINS`.

### Worker service

1차 릴리즈 코드에는 ScheduleRun in-process execution path가 있습니다. Railway에는 worker service를 별도로 만들 수 있도록 준비하되, Redis queue worker 완성은 후속 hardening으로 둡니다.

Recommended later start command:

```powershell
python -m work_schedule_ai.worker.queue_worker
```

Required future variables:

- `DATABASE_URL`
- `REDIS_URL`
- `APP_ENV`

## Database

Add a Railway PostgreSQL service and expose its internal connection URL to the API service as `DATABASE_URL`.

Migration is run by `preDeployCommand`:

```powershell
python -m alembic upgrade head
```

Local verification can use SQLite:

```powershell
$env:DATABASE_URL='sqlite:///work/tasks/2026-06-24-m6-railway-release-assets/railway-smoke.sqlite3'
python -m alembic upgrade head
python -m scripts.seed_demo
```

## Demo Seed

Seed command:

```powershell
python -m scripts.seed_demo
```

Seeded data:

- organization: `org_demo_p0`
- employees: `E001` Kim, `E002` Lee, `E003` Park, `E004` Choi
- roles: `사수`, `부사수`
- vacation: `E002` on 2026-07-01
- pair constraint: `E001` and `E002` blocked, override allowed
- ScheduleRun: approved/recalculated P0 run for 2026-07-01 through 2026-07-07
- SchedulePublication: published, read-only demo publication

The seed is idempotent and can be rerun after deploy.

## Smoke Checks

API:

```powershell
curl https://<api-domain>/health
curl https://<api-domain>/contracts/m0/summary
```

Frontend:

```text
Open https://<frontend-domain>
Run the P0 demo flow and confirm Excel download.
```

Excel:

```text
GET /organizations/org_demo_p0/schedule-publications/publication_demo_p0/excel
```
