# Handoff

## 현재 상태

상극 조합 단건 생성 API 구현과 집중/전체 테스트를 완료했습니다.

## 추가된 파일

- `src/work_schedule_ai/api/routes/pair_constraints.py`
- `tests/api/test_pair_constraints_api.py`

## 수정된 파일

- `src/work_schedule_ai/api/app.py`

## 다음 단계

1. P0의 1주 근무표 생성 mock/solver 계약 흐름을 TDD로 진행합니다.
2. 완화안 승인과 재계산 라운드 제한 계약을 이어서 구현합니다.

## 검증 요약

- RED: 4개 테스트가 라우트 없음 404로 실패했습니다.
- GREEN: `python -m pytest tests/api/test_pair_constraints_api.py -q` 결과 4 passed
- 전체 테스트: `python -m pytest -q` 결과 38 passed
- diff 검사: `git diff --check` exit 0
