# V1/V2 Development Handoff

## 현재 상태

Redis worker 분리 구현을 커밋했고, Phase 2의 첫 단위로 proposal 후보 부재 이유와 다중 휴가 override 후보 생성을 구현했습니다.

## 중요한 관찰

- 현재 브랜치와 HEAD는 `feature/m1-scaffold-contract-tests` / `dfb414a Complete first release hardening gates`입니다.
- 기존 unstaged review/memory 파일은 사용자 지시대로 건드리지 않았습니다.
- 저장소에 `AGENTS.md` 파일은 없으며, 사용자 메시지에 포함된 AGENTS 지침을 적용해야 합니다.
- 현재 `create_schedule_run`은 ScheduleRun과 snapshot을 만든 뒤 같은 요청 안에서 `execute_schedule_run(db_session, run.id, executor=_execute_schedule_run_artifacts)`를 호출합니다.
- `src/work_schedule_ai/worker/queue.py`에 in-memory/Redis queue adapter를 추가했습니다.
- `src/work_schedule_ai/worker/queue_worker.py`에 `python -m work_schedule_ai.worker.queue_worker` entrypoint를 추가했습니다.
- API/P0 테스트는 fake queue를 설치하고 결과가 필요한 시점에 worker consume을 명시적으로 호출합니다.
- `ImpactPreview.unavailable_reasons`를 추가했습니다.
- 휴가 override 후보가 여러 명이면 `approve_time_off_override` proposal을 여러 개 반환합니다.
- 같은 이슈를 해결하는 복수 후보 proposal에는 동일한 `group_id`를 부여합니다.
- 자동 후보가 없으면 manual review proposal과 diagnostic event metadata에 `NO_TIME_OFF_OVERRIDE_CANDIDATE`가 남습니다.
- `audit_logs` table/model/migration을 추가했습니다.
- `POST /organizations/{organization_id}/schedule-runs/{schedule_run_id}/manual-edits`가 manual Assignment를 저장하고 audit row를 남깁니다.
- 재계산 시 locked manual Assignment가 solver 결과를 대체해 유지됩니다.
- `src/work_schedule_ai/solver/large_cases.py`에 100명/31일 deterministic fixture generator를 추가했습니다.
- `tests/solver/test_large_schedule_performance.py`가 100명/31일 solver runtime을 10초 미만으로 회귀 검증합니다.
- 현재 측정 runtime은 약 0.0543초이며 병목은 확인되지 않았습니다.
- `/operations/schedule-runs/metrics`가 ScheduleRun status counts, active runs, 완료 평균 duration을 반환합니다.
- `/health/ready`가 database와 Redis readiness를 분리해서 반환합니다.

## 다음 작업

1. Phase 5 full 검증과 커밋을 진행합니다.
2. 완료 전 `superpowers:verification-before-completion`을 적용해 최종 점검합니다.
