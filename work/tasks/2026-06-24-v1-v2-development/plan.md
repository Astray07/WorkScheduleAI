# V1/V2 Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Use superpowers:test-driven-development before behavior changes, and superpowers:verification-before-completion before completion.

**Goal:** 1차 릴리즈 완료 후보 위에 Redis worker, 고급 진단, 수동 편집 저장/감사, 100명/31일 성능, 운영 모니터링을 순차적으로 구현합니다.

**Architecture:** 기존 FastAPI/SQLAlchemy/OR-Tools 구조를 유지하되, CPU-bound solver 실행을 API request path에서 Redis-backed worker process로 분리합니다. 이후 진단/완화안, 수동 편집, 성능, 모니터링은 ScheduleRun artifact와 audit/event 기록을 확장하는 방식으로 붙입니다.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, PostgreSQL/SQLite tests, Redis queue, OR-Tools CP-SAT, pytest, Vite/React.

---

## Phase 1: Redis Worker Separation

- [x] 현재 in-process ScheduleRun 실행 테스트와 API 기대값을 확정합니다.
- [x] Redis enqueue 추상화와 fake/in-memory queue test double을 설계합니다.
- [x] API `POST /schedule-runs`가 ScheduleRun/Snapshot만 생성하고 job enqueue 후 `202 queued` 응답을 반환하도록 failing test를 작성합니다.
- [x] worker entrypoint가 Redis job을 받아 DB session을 열고 기존 `execute_schedule_run(..., executor=...)` 경계를 호출하도록 failing test를 작성합니다.
- [x] enqueue idempotency, duplicate enqueue 방지, canceled run skip, worker technical retry가 `current_attempt_no`만 증가하는지 검증합니다.
- [x] 최소 구현으로 API path에서 solver 직접 실행을 제거합니다.
- [x] Railway API/worker start command와 `REDIS_URL` 문서를 갱신합니다.
- [x] focused tests, full pytest, frontend build, diff check를 실행하고 문서화합니다.

## Phase 2: Advanced Diagnostics And Mitigations

- [x] 현재 SolverDiagnosticEvent와 proposal 생성 경계를 정리합니다.
- [x] assumption literal 기반 또는 동등한 구조화 진단이 필요한 케이스를 테스트로 고정합니다.
- [x] 완화안이 2개 미만일 때 추가 후보 부재 이유를 API에 노출합니다.
- [x] grouped proposal과 requires_proposal_ids를 읽기 전용/수동 조정 폴백 UX 계약에 맞게 실제화합니다.
- [x] LLM 설명 payload가 서버 구조화 진단만 자연어화하고 개인정보와 numeric loss score를 보내지 않는지 회귀 테스트합니다.

## Phase 3: Manual Edit Persistence And Audit

- [x] 기존 manual edit validation API의 통과/실패 케이스를 재확인합니다.
- [x] 수동 편집 저장 API가 Assignment source/manual, locked_by_user, warning_state를 영속화하는 테스트를 추가합니다.
- [x] 편집 이벤트와 override/manual lock 감사 이력을 별도 audit record로 남깁니다.
- [x] 재계산 시 manual lock이 유지되고 recalculation_count 한도와 충돌하지 않는지 검증합니다.
- [x] published SchedulePublication 이후 편집 저장이 거부되는지 검증합니다.

## Phase 4: 100 Employees / 31 Days Performance Hardening

- [ ] 100명/31일 fixture generator와 deterministic benchmark를 추가합니다.
- [ ] 현재 solver runtime, artifact row count, DB write count를 baseline으로 기록합니다.
- [ ] 병목이 확인된 부분만 최적화합니다.
- [ ] 재현성 우선 모드와 빠른 생성 모드의 solver parameter 차이를 명시합니다.
- [ ] 성능 기준과 남은 리스크를 문서화합니다.

## Phase 5: Operational Monitoring

- [ ] ScheduleRun phase/status/duration metric과 실패 reason code를 기록합니다.
- [ ] worker heartbeat 또는 job processing visibility를 추가합니다.
- [ ] health/readiness endpoint가 DB와 Redis 연결 상태를 구분해 보고하도록 확장합니다.
- [ ] 운영 smoke checklist를 작성하고 마지막 통합 점검 전까지 push/deploy는 보류합니다.

## Redis Worker 성공 기준

- API는 ScheduleRun 생성 시 solver를 직접 실행하지 않고 Redis job enqueue까지만 수행합니다.
- `POST /organizations/{organization_id}/schedule-runs` 응답은 즉시 `202`와 `status="queued"`를 반환합니다.
- worker process는 같은 ScheduleRun id를 받아 기존 solver artifact 저장 경계를 실행하고 `running -> succeeded/infeasible/failed/canceled` 상태 전이를 유지합니다.
- idempotency key 재사용은 기존 동작을 유지하며, 같은 입력은 기존 run 반환, 다른 snapshot hash는 `409`를 반환합니다.
- worker technical retry는 `current_attempt_no`만 증가시키고 `recalculation_count`는 증가시키지 않습니다.
- 취소된 run은 worker가 solver를 실행하지 않습니다.
- 테스트에서는 실제 Redis 없이 fake queue로 API enqueue와 worker consume을 검증하고, Redis client 의존성은 얇은 adapter 뒤에 둡니다.
- Railway 문서에는 API service와 worker service의 별도 start command, `DATABASE_URL`, `REDIS_URL` 요구사항이 반영됩니다.

## Redis Worker 검증 방법

- `python -m pytest tests/worker/test_schedule_worker.py -q`
- `python -m pytest tests/api/test_schedule_runs_api.py -q`
- 신규 queue adapter/entrypoint 테스트를 포함한 focused worker/API 테스트
- `python -m pytest -q`
- `cd frontend; npm run build`
- `git diff --check`
