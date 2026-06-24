# V1/V2 Development Decisions

## 1. Redis worker부터 진행

릴리즈 체크리스트와 이전 handoff 모두 Redis queue 기반 별도 solver worker를 후속 hardening의 첫 항목으로 둡니다. 현재 API가 request path에서 `execute_schedule_run(..., executor=...)`를 직접 호출하므로, CPU-bound solver 분리와 Railway API/worker 분리가 가장 먼저 필요합니다.

## 2. 기존 worker-compatible 경계를 재사용

`src/work_schedule_ai/worker/schedule_worker.py`의 `execute_schedule_run` 함수는 ScheduleRun 상태 전이와 executor callback 경계를 이미 갖고 있습니다. Redis 작업은 새 solver를 만들지 않고 이 경계를 queue consumer에서 호출하는 방향으로 진행합니다.

## 3. 테스트에서는 fake queue를 우선 사용

로컬 기본 검증을 안정적으로 유지하기 위해 API enqueue와 worker consume은 fake/in-memory queue adapter로 먼저 고정합니다. 실제 Redis 연결 검증은 adapter 단위 또는 환경 변수가 있는 integration test로 분리합니다.

## 4. AGENTS.md는 사용자 제공 지침으로 대체

저장소 루트에서 `AGENTS.md` 파일은 발견되지 않았습니다. 사용자 메시지의 AGENTS 지침을 현재 작업의 authoritative instruction으로 적용합니다.

## 5. API 기본 동작은 queued 응답으로 변경

기존 1차 릴리즈 후보는 API 요청 안에서 ScheduleRun을 즉시 실행했습니다. Redis worker 분리 이후 `POST /schedule-runs`는 `queued` 상태를 반환하고, 테스트에서 결과가 필요한 경우 fake queue를 명시적으로 consume합니다.

## 6. Worker entrypoint는 기존 artifact executor를 재사용

`python -m work_schedule_ai.worker.queue_worker`는 Redis 또는 fake queue에서 run id를 소비하고 `execute_schedule_run`을 호출합니다. artifact 생성 로직은 현재 `schedule_runs` route의 기존 `_execute_schedule_run_artifacts` 경계를 재사용해 범위 확장을 피했습니다.

## 7. Phase 2 첫 단위는 proposal 후보 이유와 다중 후보 생성으로 제한

전체 assumption literal 진단 모델은 큰 변경이므로 먼저 API 사용자 가치가 바로 드러나는 구조화 이유를 추가했습니다. `ImpactPreview.unavailable_reasons`는 기존 `impact_preview_json`에 저장되어 별도 migration 없이 응답과 diagnostic metadata에 함께 남습니다.

## 8. Manual edit audit는 별도 AuditLog 테이블로 저장

수동 편집은 `Assignment.source="manual"`과 `locked_by_user=true`를 직접 영속화하고, 변경 사실은 `audit_logs`에 별도 row로 남깁니다. AuditLog는 민감 원문을 저장하지 않고 schedule_run_id, slot_id, role_id, employee_id, warning code 정도의 구조화 metadata만 기록합니다.

## 9. 재계산은 locked manual assignment를 solver 결과에 병합

재계산 artifact 교체 시 기존 `source=manual`, `locked_by_user=true` assignment를 먼저 읽어 같은 slot/role 또는 slot/employee solver assignment를 대체합니다. 이 방식은 solver 모델을 즉시 크게 바꾸지 않고도 사용자 수동 잠금을 보존합니다.
