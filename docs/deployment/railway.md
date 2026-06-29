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
- `REDIS_URL`: Railway Redis internal connection URL used to enqueue ScheduleRun jobs
- `CORS_ALLOW_ORIGINS`: deployed frontend origin, comma-separated for multiple origins
- `APP_ENV`: `production`

Optional variables:

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

ScheduleRun solver execution runs outside the API request path. Create a separate Railway worker service from the same repository. The root `railway.json` is intentionally API-only; do not reuse its API start command for the worker service.

Start:

```powershell
python -m work_schedule_ai.worker.queue_worker
```

The same command is captured in `railway.worker.json` for copy/paste or service-level config import:

```json
"startCommand": "sh -c 'python -m work_schedule_ai.worker.queue_worker'"
```

Required variables:

- `DATABASE_URL`
- `REDIS_URL`
- `APP_ENV`

The API service creates `ScheduleRun` rows and enqueues run ids into Redis. The worker service consumes those ids, opens its own database session, runs the OR-Tools artifact executor, and transitions the run from `queued` to a terminal state.

Freshness check:

1. Open the API service public URL and call `/health/version`.
2. Open the worker service deployment logs.
3. Confirm the first log line starts with `Starting schedule queue worker` and the JSON `git_commit` matches the API `/health/version` commit.

If the commits differ, redeploy the worker service or confirm the worker service is attached to the same GitHub branch. A stale worker can still consume Redis jobs successfully, but it may run older solver policy code and produce outdated assignment behavior.

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

## Test Login User

After setting `WORKSCHEDULEAI_SIGNED_ACTOR_SECRET` on the API service, create a
temporary login user from the API service runtime:

```powershell
python -m scripts.seed_login_user
```

Default credentials target:

- organization id: `org_demo_p0`
- email: `demo.admin@example.com`
- role: `admin`

If `WORKSCHEDULEAI_SEED_LOGIN_PASSWORD` is not set, the command generates a
temporary password and prints it once in the JSON output. To choose the password
explicitly, set this variable before running the command:

```powershell
WORKSCHEDULEAI_SEED_LOGIN_PASSWORD=<temporary-password>
python -m scripts.seed_login_user
```

Optional overrides:

- `WORKSCHEDULEAI_SEED_LOGIN_ORGANIZATION_ID`
- `WORKSCHEDULEAI_SEED_LOGIN_ORGANIZATION_NAME`
- `WORKSCHEDULEAI_SEED_LOGIN_EMAIL`
- `WORKSCHEDULEAI_SEED_LOGIN_NAME`
- `WORKSCHEDULEAI_SEED_LOGIN_ROLE`

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
