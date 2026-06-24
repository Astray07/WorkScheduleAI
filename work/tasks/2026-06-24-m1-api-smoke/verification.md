# Verification

## 수행한 검증

### RED 확인

명령:

```powershell
python -m pytest tests/api/test_api_smoke.py -q
```

결과: 예상대로 실패했습니다.

```text
ModuleNotFoundError: No module named 'work_schedule_ai.api'
```

### GREEN 확인

명령:

```powershell
python -m pytest tests/api/test_api_smoke.py -q
```

결과:

```text
..                                                                       [100%]
2 passed in 0.21s
```

### 전체 테스트

명령:

```powershell
python -m pytest -q
```

결과:

```text
........                                                                 [100%]
8 passed in 0.22s
```

## 결과

- `create_app()` FastAPI 앱 팩토리를 추가했습니다.
- `GET /health`를 추가했습니다.
- `GET /contracts/m0/summary`를 추가했습니다.
- M0 계약 테스트 6개와 API smoke 테스트 2개가 모두 통과했습니다.

## 남은 위험

- DB, 인증, tenant scope는 아직 검증하지 않습니다.
- 실제 M0 업무 API route는 아직 구현하지 않습니다.
- `/contracts/m0/summary`는 개발용 smoke endpoint이며 운영 공개 API로 확정한 것은 아닙니다.
