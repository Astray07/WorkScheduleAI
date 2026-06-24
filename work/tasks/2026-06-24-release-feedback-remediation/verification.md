# Release Feedback Remediation Verification

## 실행 결과

- `python -m pytest tests\api\test_schedule_runs_api.py -q`: 24 passed
- `python -m pytest tests\api\test_p0_vertical_slice_api.py tests\worker\test_schedule_worker.py tests\scripts\test_seed_demo.py -q`: 9 passed
- `python -m pytest -q`: 101 passed
- `cd frontend; npm run build`: 성공
- Playwright browser smoke: 성공
  - 로컬 `DATABASE_URL=sqlite:///work/tasks/2026-06-24-release-feedback-remediation/browser-smoke.sqlite3`로 alembic head 적용
  - FastAPI `127.0.0.1:8000`, Vite `127.0.0.1:5173` 임시 실행
  - P0 데모 생성, 완화안 승인, 재계산, 확정, 엑셀 다운로드 버튼 상태 확인
  - 검증 후 임시 서버와 browser smoke 산출물 정리
- `git diff --check`: 통과

## 확인한 성공 기준

- 프론트 P0 흐름이 `주간 근무` shift type을 생성한 뒤 ScheduleRun을 생성합니다.
- shift-template 기반 ScheduleRun 생성 응답이 `cp_sat_*` solver status를 반환합니다.
- ScheduleRun 결과 artifact가 DB row로 저장되고, 조회/발행/다운로드가 저장본을 사용합니다.
- publication은 `result_snapshot_json`을 저장하며, 직원명 변경 후 Excel 다운로드가 기존 확정본을 유지합니다.
- 같은 idempotency key가 다른 입력 snapshot으로 재사용되면 `409 SCHEDULE_RUN_IDEMPOTENCY_CONFLICT`를 반환합니다.
- Railway deploy dependency에 `psycopg[binary]`가 포함됐습니다.

## 남은 위험

- Redis queue 분리, PostgreSQL RLS, 고급 objective 전체 반영, 수동 편집 API/UI는 이번 remediation 범위 밖입니다.
- legacy shift-template 미설정 경로는 기존 테스트 호환을 위해 fallback으로 남아 있습니다.
