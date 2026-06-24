# M1 P0 Vertical Slice API Test Verification

## 집중 검증

명령:

```powershell
python -m pytest tests\api\test_p0_vertical_slice_api.py -q
```

결과:

- `1 passed`

## 남은 검증

없습니다.

## 전체 검증

명령:

```powershell
python -m pytest -q
```

결과:

- `68 passed`

명령:

```powershell
git diff --check
```

결과:

- 종료 코드 0
- 출력 없음
