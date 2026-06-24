# Handoff

## 현재 상태

FastAPI smoke API 작업을 구현했습니다.

## 추가된 파일

- `src/work_schedule_ai/api/__init__.py`
- `src/work_schedule_ai/api/app.py`
- `tests/api/test_api_smoke.py`

## 수정된 파일

- `pyproject.toml`

## 다음 단계

1. M1 도메인/테넌시 구현 계획을 작성합니다.
2. 조직/직원/역할의 DB model과 migration 테스트를 TDD로 시작합니다.
3. OpenAPI M0 path 중 `POST /organizations`부터 실제 route contract test를 연결합니다.

## 검증 요약

- RED: `ModuleNotFoundError: No module named 'work_schedule_ai.api'`
- GREEN: `python -m pytest tests/api/test_api_smoke.py -q` 결과 2 passed
- 전체 테스트: `python -m pytest -q` 결과 8 passed
