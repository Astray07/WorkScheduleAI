# Verification

## RED

- `python -m pytest tests/api/test_pair_constraints_api.py -q`
- 결과: 4 failed
- 실패 사유: `POST /organizations/org_1/pair-constraints` 라우트가 아직 없어 404로 실패했습니다.

## GREEN

- `python -m pytest tests/api/test_pair_constraints_api.py -q`
- 결과: `4 passed in 0.47s`

## 전체 회귀

- `python -m pytest -q`
- 결과: `38 passed in 1.14s`

## Diff 검사

- `git diff --check`
- 결과: exit 0
- 참고: `src/work_schedule_ai/api/app.py`에 대해 Git CRLF 변환 경고가 출력되었지만 whitespace error는 없었습니다.
