# Handoff

## 현재 상태

M1 전 단계로 Python 스캐폴딩과 계약 테스트 기반을 추가했습니다. 현재 브랜치는 `feature/m1-scaffold-contract-tests`입니다.

## 추가된 파일

- `pyproject.toml`
- `.gitignore`
- `src/work_schedule_ai/__init__.py`
- `src/work_schedule_ai/contracts.py`
- `tests/contracts/test_m0_contract.py`

## 다음 단계

1. FastAPI 의존성을 추가하고 `GET /health`와 OpenAPI 기반 smoke API를 TDD로 만듭니다.
2. M0 OpenAPI schema와 FastAPI route 응답 shape를 맞추는 contract test를 추가합니다.
3. 이후 SQLAlchemy/Alembic 스캐폴딩과 DB invariant 테스트로 넘어갑니다.

## 검증 요약

- RED: `ModuleNotFoundError: No module named 'work_schedule_ai'`
- GREEN: `python -m pytest tests/contracts/test_m0_contract.py -q` 결과 6 passed
- 전체 테스트: `python -m pytest -q` 결과 6 passed
