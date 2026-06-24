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
- 자동 후보가 없으면 manual review proposal과 diagnostic event metadata에 `NO_TIME_OFF_OVERRIDE_CANDIDATE`가 남습니다.

## 다음 작업

1. Phase 2 focused/full 검증을 실행합니다.
2. proposal 후보 이유/다중 후보 변경을 커밋합니다.
3. grouped proposal/read-only fallback 또는 LLM 설명 회귀 테스트를 다음 단위로 진행합니다.
