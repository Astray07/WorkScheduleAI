# M2 ScheduleRun Solver API Verification

## RED 확인

명령:

```powershell
python -m pytest tests\api\test_schedule_runs_api.py -q
```

결과:

- `1 failed, 19 passed`
- 실패 이유: shift template이 있어도 기존 mock path가 사용되어 첫 번째 부사수 요구가 강제로 미배정 처리됐습니다.

## 집중 GREEN 확인

명령:

```powershell
python -m pytest tests\api\test_schedule_runs_api.py tests\api\test_p0_vertical_slice_api.py -q
```

결과:

- `21 passed`

## 남은 검증

없습니다.

## 전체 검증

명령:

```powershell
python -m pytest -q
```

결과:

- `82 passed`

명령:

```powershell
git diff --check
```

결과:

- 종료 코드 0
- CRLF 변환 경고만 출력되었습니다.
