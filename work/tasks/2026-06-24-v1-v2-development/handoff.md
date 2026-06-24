# V1/V2 Development Handoff

## 현재 상태

Redis worker 분리 구현을 진행했습니다. API는 ScheduleRun 생성 시 solver를 직접 실행하지 않고 fake/Redis queue에 run id를 enqueue하며 `queued` 응답을 반환합니다.

## 중요한 관찰

- 현재 브랜치와 HEAD는 `feature/m1-scaffold-contract-tests` / `dfb414a Complete first release hardening gates`입니다.
- 기존 unstaged review/memory 파일은 사용자 지시대로 건드리지 않았습니다.
- 저장소에 `AGENTS.md` 파일은 없으며, 사용자 메시지에 포함된 AGENTS 지침을 적용해야 합니다.
- 현재 `create_schedule_run`은 ScheduleRun과 snapshot을 만든 뒤 같은 요청 안에서 `execute_schedule_run(db_session, run.id, executor=_execute_schedule_run_artifacts)`를 호출합니다.
- `src/work_schedule_ai/worker/queue.py`에 in-memory/Redis queue adapter를 추가했습니다.
- `src/work_schedule_ai/worker/queue_worker.py`에 `python -m work_schedule_ai.worker.queue_worker` entrypoint를 추가했습니다.
- API/P0 테스트는 fake queue를 설치하고 결과가 필요한 시점에 worker consume을 명시적으로 호출합니다.

## 다음 작업

1. frontend build와 `git diff --check`를 실행합니다.
2. Redis worker 변경을 커밋합니다.
3. Phase 2 고급 진단/완화안 실제화를 TDD로 시작합니다.
