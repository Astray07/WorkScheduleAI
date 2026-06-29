# Demo And Deployment Checklist

확인일: 2026-06-29

이 체크리스트는 과제 제출/시연용입니다. 목표 상태는 "상용 완제품 출시"가 아니라 "파일럿 운영 가능한 수준의 운영 검증용 시연"입니다.

## 1. 제출 패키지 확인

- [ ] `README.md`가 프로젝트 개요, 실행, Railway, 테스트, 시연 흐름, 한계를 포함한다.
- [ ] `docs/submission-report.md`가 목표, 배경, 구조, 기능, RAG, 제약 로직, 안정성, 검증, 의사결정, 한계를 포함한다.
- [ ] `docs/release/demo-deployment-checklist.md`가 로컬 시연과 Railway 확인 절차를 포함한다.
- [ ] `docs/deployment/railway.md`가 API, worker, frontend, PostgreSQL, Redis 구성을 설명한다.
- [ ] 제출 설명에서 "상용 완제품" 대신 "파일럿 운영 가능한 수준", "운영 검증용", "인사담당자 검토 기반"을 사용한다.

## 2. 로컬 시연 준비

Backend:

```powershell
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m scripts.seed_demo
python -m uvicorn work_schedule_ai.api.app:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

Worker:

```powershell
python -m work_schedule_ai.worker.queue_worker
```

Frontend:

```powershell
cd frontend
npm install
$env:VITE_API_BASE_URL='http://127.0.0.1:8000'
npm run dev
```

Optional login seed:

```powershell
python -m scripts.seed_login_user
```

## 3. 로컬 검증

- [ ] `python -m pytest -q`
- [ ] `cd frontend; npm test`
- [ ] `cd frontend; npm run build`
- [ ] `git diff --check`
- [ ] 필요 시 `python -m pytest tests\deployment\test_deployment_docs.py tests\deployment\test_railway_config.py -q`

선택 검증:

- [ ] `TEST_POSTGRES_URL`을 설정한 뒤 PostgreSQL RLS integration test 실행
- [ ] 실제 Redis를 연결한 API/worker enqueue/dequeue smoke 실행
- [ ] `RUN_SOLVER_HARDENING_BENCHMARK=1`로 고제약 benchmark 실행

## 4. 시연 플로우

1. "이 시스템은 인사담당자 검토 기반의 AI 근무표 작성 도구"라고 소개한다.
2. 직원, 역할, 휴가, 상극 조합, 근무 유형 입력 영역을 보여준다.
3. 근무표 생성을 실행한다.
4. ScheduleRun이 queue를 거쳐 worker에서 처리되는 구조를 설명한다.
5. 결과 그리드에서 배정, 미배정 이슈, 완화 후보를 보여준다.
6. "판단 근거" 영역에서 사내 규정 근거와 safety note를 확인한다.
7. 예외 승인 또는 수동 수정 검증을 보여준다.
8. 재계산 후 결과가 바뀌는 흐름을 보여준다.
9. 확정 버튼으로 SchedulePublication을 만들고 읽기 전용 상태를 설명한다.
10. Excel 다운로드와 audit log를 보여준다.
11. 마지막에 현재 한계와 파일럿 검증 후속 과제를 명확히 말한다.

## 5. Railway 서비스 구성

API service:

- [ ] Root directory: repository root
- [ ] Config: `railway.json`
- [ ] Builder: Dockerfile
- [ ] Pre-deploy: `python -m alembic upgrade head`
- [ ] Start: `python -m uvicorn work_schedule_ai.api.app:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}`
- [ ] Healthcheck path: `/health/ready`

Worker service:

- [ ] Root directory: repository root
- [ ] Config reference: `railway.worker.json`
- [ ] Start: `python -m work_schedule_ai.worker.queue_worker`
- [ ] API와 같은 `DATABASE_URL`, `REDIS_URL`, `WORKSCHEDULEAI_SIGNED_ACTOR_SECRET` 사용
- [ ] `WORKSCHEDULEAI_QUEUE_LEASE_SECONDS`는 solver 최대 timeout 120초보다 크게 설정한다. 기본 권장값은 900초다.

Frontend service:

- [ ] Root directory: `frontend`
- [ ] Config: `frontend/railway.json`
- [ ] Build: `npm install --include=dev && npm run build`
- [ ] Start: `npm run preview -- --host 0.0.0.0 --port ${PORT:-4173}`
- [ ] `VITE_API_BASE_URL=https://<api-domain>` 설정

Data services:

- [ ] Railway PostgreSQL service 생성
- [ ] Railway Redis service 생성
- [ ] API/worker가 internal `DATABASE_URL`, `REDIS_URL`을 사용하도록 설정

## 6. Railway 환경변수 체크

API:

- [ ] `APP_ENV=production`
- [ ] `DATABASE_URL=<Railway PostgreSQL internal URL>`
- [ ] `REDIS_URL=<Railway Redis internal URL>`
- [ ] `CORS_ALLOW_ORIGINS=https://<frontend-domain>`
- [ ] `WORKSCHEDULEAI_AUTH_REQUIRED=1`
- [ ] `WORKSCHEDULEAI_SIGNED_ACTOR_SECRET=<32+ chars>`
- [ ] `WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET=<32+ chars>`

Worker:

- [ ] `APP_ENV=production`
- [ ] `DATABASE_URL=<same PostgreSQL URL>`
- [ ] `REDIS_URL=<same Redis URL>`
- [ ] `WORKSCHEDULEAI_AUTH_REQUIRED=1`
- [ ] `WORKSCHEDULEAI_SIGNED_ACTOR_SECRET=<same as API>`
- [ ] `WORKSCHEDULEAI_QUEUE_LEASE_SECONDS=900`

Frontend:

- [ ] `VITE_API_BASE_URL=https://<api-domain>`

## 7. Railway 최신 배포 확인 방법

공식 Railway 문서 확인 기준:

- Deployments reference: https://docs.railway.com/deployments/reference
- Healthchecks: https://docs.railway.com/deployments/healthchecks
- CLI logs: https://docs.railway.com/cli/logs
- CLI deploy flow: https://docs.railway.com/cli/deploying

Dashboard 확인:

- [ ] API, worker, frontend 각 서비스의 최신 deployment 상태가 `Active`인지 확인한다.
- [ ] API service는 `/health/ready` healthcheck가 성공해야 한다.
- [ ] Railway healthcheck는 deployment 활성화 전 HTTP 200 응답을 기다리지만, 활성화 후 지속 모니터링 용도는 아니므로 별도 smoke가 필요하다.
- [ ] Deployment logs에서 build/deploy error가 없는지 확인한다.
- [ ] Worker logs 첫 줄이 `Starting schedule queue worker`로 시작하는지 확인한다.

CLI 확인 예시:

```powershell
railway logs --service <api-service-name> --latest --lines 100
railway logs --service <worker-service-name> --latest --lines 100
railway logs --service <frontend-service-name> --latest --lines 100
```

API/worker freshness check:

```powershell
curl https://<api-domain>/health/version
railway logs --service <worker-service-name> --latest --lines 20
```

- [ ] API `/health/version`의 `git_commit`을 확인한다.
- [ ] Worker 시작 로그의 `git_commit`과 API commit이 같은지 확인한다.
- [ ] commit이 다르면 worker service가 같은 branch/source를 바라보는지 확인하고 redeploy한다.

API smoke:

```powershell
curl https://<api-domain>/health/ready
curl https://<api-domain>/contracts/m0/summary
```

Frontend smoke:

- [ ] `https://<frontend-domain>` 접속
- [ ] 배포 설정 오류 없이 첫 화면 렌더링
- [ ] P0 demo flow에서 근무표 생성, 이슈/완화 후보 확인, 확정, Excel 다운로드 확인

Queue smoke:

- [ ] API에서 ScheduleRun 생성
- [ ] Worker logs에서 job 처리 로그 확인
- [ ] ScheduleRun이 `queued` 또는 `running`에 오래 머물지 않고 terminal 상태로 전환되는지 확인
- [ ] 오래 stuck된 run이 있으면 `python -m scripts.requeue_queued_schedule_runs` 절차를 검토

## 8. Signoff 기준

제출/시연 signoff:

- [ ] README와 제출 보고서가 최신 상태다.
- [ ] 로컬 테스트와 frontend build가 통과한다.
- [ ] 시연 플로우를 한 번 이상 끝까지 수행했다.
- [ ] 남은 위험을 숨기지 않고 보고서와 발표에 포함했다.

Railway 파일럿 signoff:

- [ ] API, worker, frontend 최신 deployment가 모두 `Active`다.
- [ ] API와 worker commit이 일치한다.
- [ ] PostgreSQL migration이 성공했다.
- [ ] 실제 Redis queue를 통한 ScheduleRun이 성공한다.
- [ ] PostgreSQL RLS integration signoff를 실행했다.
- [ ] production 필수 환경변수 누락이 없다.
- [ ] 관리자 인증과 tenant context가 켜져 있다.

## 9. 말하지 말아야 할 표현

- "완전 자동 근무표 확정"
- "상용 운영 완성"
- "법률 준수 자동 보증"
- "실제 운영에서 모든 규모 검증 완료"
- "LLM이 근무 규정을 자동으로 바꾼다"

권장 표현:

- "파일럿 운영 가능한 수준"
- "운영 검증용"
- "인사담당자 검토 기반"
- "제약 최적화와 RAG 근거 제시를 결합한 시연/파일럿 후보"
- "공개 SaaS 출시 전 추가 검증이 필요한 상태"
