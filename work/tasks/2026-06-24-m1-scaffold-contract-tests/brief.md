# Brief

## 목표

M1 착수 전에 Python 프로젝트 스캐폴딩과 계약 테스트 기반을 만듭니다. M0에서 작성한 OpenAPI와 fixture가 이후 FastAPI, worker, frontend mock 개발의 기준이 되도록 자동 검증 가능한 최소 테스트 하네스를 준비합니다.

## 비목표

- 실제 FastAPI route 구현은 하지 않습니다.
- 실제 DB 연결, SQLAlchemy model, Alembic migration은 만들지 않습니다.
- OR-Tools solver 구현은 하지 않습니다.
- frontend 앱은 아직 만들지 않습니다.

## 성공 기준

- `pyproject.toml`에 Python 패키지와 pytest 설정이 생깁니다.
- `src/work_schedule_ai/contracts.py`가 M0 OpenAPI와 fixture를 로드하고 필수 계약을 검증합니다.
- `tests/contracts/test_m0_contract.py`가 P0 필수 path, 핵심 schema, fixture JSON, fixture 상태를 검증합니다.
- 테스트는 RED 실패를 먼저 확인한 뒤 GREEN 통과합니다.

## 제약

- TDD 순서를 지킵니다.
- 코드 변경은 스캐폴딩과 계약 테스트에 한정합니다.
- M0 계약 자체를 임의로 확장하지 않습니다.
- 앱 코드가 없는 상태이므로 외부 서비스 의존 없이 로컬 파일 기반 테스트만 작성합니다.

