# First Release Execution Verification

## 초기 확인

명령:

```powershell
git status --short --branch
```

결과:

- `## feature/m1-scaffold-contract-tests`
- 작업 트리 변경 없음

명령:

```powershell
@'
try:
    import ortools
    print('ortools installed', getattr(ortools, '__version__', 'unknown'))
except Exception as exc:
    print('ortools missing', type(exc).__name__, exc)
'@ | python -
```

결과:

- `ortools missing ModuleNotFoundError No module named 'ortools'`

## 남은 검증

- 각 하위 작업 완료 시 focused test와 전체 test를 기록합니다.
- M6 Railway release assets:
  - `python -m pytest tests\scripts\test_seed_demo.py -q` -> `2 passed`
  - `python -m pytest tests\api\test_api_smoke.py -q` -> `3 passed`
  - temp `DATABASE_URL`로 `python -m alembic upgrade head` 및 `python -m scripts.seed_demo` 성공
  - `python -m pytest -q` -> `97 passed`
  - `cd frontend; npm run build` -> 통과
  - `git diff --check` -> exit 0
  - Docker build는 Docker Desktop Linux engine daemon 미실행으로 로컬 확인 불가

## 최종 HEAD 검증

명령:

```powershell
python -m pytest -q
cd frontend
npm run build
git diff --check
git status --short --branch
```

결과:

- `97 passed in 4.23s`
- frontend TypeScript/Vite build 통과
- `git diff --check` exit 0
- `## feature/m1-scaffold-contract-tests`
- 작업 트리 변경 없음
