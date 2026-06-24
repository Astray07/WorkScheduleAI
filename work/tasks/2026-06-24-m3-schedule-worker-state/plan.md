# M3 Schedule Worker State Plan

- [x] 범위와 성공 기준을 정리합니다.
- [x] 실패 테스트를 작성하고 RED를 확인합니다.
- [x] worker 함수와 cancel API를 구현합니다.
- [x] ScheduleRun create 흐름에 queued 후 in-process execute를 반영합니다.
- [x] focused test와 전체 test를 실행합니다.
- [x] 변경을 커밋합니다.

## 검증 방법

- `python -m pytest tests/worker/test_schedule_worker.py tests/api/test_schedule_runs_api.py -q`
- `python -m pytest -q`
- `git diff --check`
