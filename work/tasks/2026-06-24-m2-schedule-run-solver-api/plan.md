# M2 ScheduleRun Solver API Plan

- [x] 범위와 성공 기준을 정리합니다.
- [x] 실패 테스트를 작성하고 RED를 확인합니다.
- [x] ScheduleRun result builder에 OR-Tools path를 추가합니다.
- [x] 기존 mock path 회귀를 확인합니다.
- [x] 전체 테스트와 `git diff --check`를 실행합니다.
- [x] 변경을 커밋합니다.

## 검증 방법

- `python -m pytest tests/api/test_schedule_runs_api.py -q`
- `python -m pytest tests/api/test_schedule_runs_api.py tests/api/test_p0_vertical_slice_api.py -q`
- `python -m pytest -q`
- `git diff --check`
