# M2 OR-Tools Solver Foundation Plan

- [x] 범위와 성공 기준을 정리합니다.
- [x] solver 실패 테스트를 작성하고 RED를 확인합니다.
- [x] OR-Tools 의존성을 추가하고 설치/import를 확인합니다.
- [x] solver DTO와 CP-SAT 구현을 추가합니다.
- [x] focused test와 전체 test를 실행합니다.
- [x] 변경을 커밋합니다.

## 검증 방법

- `python -m pytest tests/solver/test_ortools_solver.py -q`
- `python -m pytest -q`
- `git diff --check`
