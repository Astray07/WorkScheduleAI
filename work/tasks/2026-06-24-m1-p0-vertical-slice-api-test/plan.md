# M1 P0 Vertical Slice API Test Plan

- [x] 범위와 성공 기준을 정리합니다.
- [x] P0 vertical slice API 테스트를 추가합니다.
- [x] 집중 테스트를 실행합니다.
- [x] 전체 테스트와 `git diff --check`를 실행합니다.
- [x] 변경을 커밋합니다.

## 검증 방법

- `python -m pytest tests/api/test_p0_vertical_slice_api.py -q`
- `python -m pytest -q`
- `git diff --check`
