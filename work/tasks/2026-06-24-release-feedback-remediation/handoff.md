# Release Feedback Remediation Handoff

## 현재 상태

리뷰 피드백 중 P0/P1 차단 항목을 우선 반영했습니다.

- 결과 artifact 테이블과 alembic revision `20260624_0008`을 추가했습니다.
- ScheduleRun 생성/재계산이 worker executor를 통해 solver artifact를 계산하고 저장합니다.
- result/publication/excel 경로가 저장 artifact 또는 publication snapshot을 사용합니다.
- `ScheduleInputSnapshot` payload에 shift type, requirement, employee role, unavailability, pair constraint를 포함합니다.
- 같은 idempotency key가 다른 snapshot으로 들어오면 `409`를 반환합니다.
- 프론트 P0 흐름이 shift type을 생성해 실제 solver path를 탑니다.
- deploy dependency에 `psycopg[binary]`를 추가했습니다.

## 다음 단계

1. 커밋 전 `git diff`를 최종 점검합니다.
2. 관련 파일만 stage/commit합니다. `docs/.bkit-memory.json`과 `work/tasks/2026-06-24-product-plan-review/*` 변경은 기존/리뷰 산출물이므로 제외합니다.
3. 후속 hardening으로 Redis worker 분리, PostgreSQL RLS, 고급 objective/진단, 수동 편집 API/UI를 별도 계획으로 진행합니다.
