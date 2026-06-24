# Verification

## 수행한 검증

### RED 확인

명령:

```powershell
python -m pytest tests/contracts/test_m0_contract.py -q
```

결과: 예상대로 실패했습니다.

```text
ModuleNotFoundError: No module named 'work_schedule_ai'
```

### GREEN 확인

명령:

```powershell
python -m pytest tests/contracts/test_m0_contract.py -q
```

결과:

```text
......                                                                   [100%]
6 passed in 0.02s
```

### 전체 테스트

명령:

```powershell
python -m pytest -q
```

결과:

```text
......                                                                   [100%]
6 passed in 0.02s
```

## 결과

- 계약 테스트를 먼저 작성했고, 패키지가 없어 실패하는 RED 상태를 확인했습니다.
- `pyproject.toml`, `src/work_schedule_ai/__init__.py`, `src/work_schedule_ai/contracts.py`를 추가했습니다.
- M0 OpenAPI path/schema와 fixture 상태를 검증하는 테스트 6개가 통과했습니다.

## 남은 위험

- 이번 단계는 OpenAPI semantic validator가 아니라 로컬 계약 로더 테스트입니다.
- FastAPI, SQLAlchemy, Alembic은 아직 도입하지 않았으므로 실제 API/DB 동작은 후속 단계에서 검증해야 합니다.
- fixture가 OpenAPI schema와 완전히 일치하는지는 아직 엄격 검증하지 않습니다. 후속 단계에서 JSON Schema 기반 contract validation을 추가해야 합니다.
