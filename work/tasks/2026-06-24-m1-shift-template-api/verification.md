# M1 Shift Template API Verification

## RED 확인

명령:

```powershell
python -m pytest tests\db\test_domain_models.py tests\db\test_alembic_migrations.py tests\api\test_shift_templates_api.py -q
```

결과:

- `10 failed, 23 passed`
- 실패 이유: `ShiftType`, `ShiftRequirement`, `shift_types`, `shift_requirements`, 0007 migration, `/shift-types` route가 없었습니다.

## 집중 GREEN 확인

명령:

```powershell
python -m pytest tests\db\test_domain_models.py tests\db\test_alembic_migrations.py tests\api\test_shift_templates_api.py -q
```

결과:

- `33 passed`

## 남은 검증

없습니다.

## 전체 검증

명령:

```powershell
python -m pytest -q
```

결과:

- `75 passed`

명령:

```powershell
git diff --check
```

결과:

- 종료 코드 0
- CRLF 변환 경고만 출력되었습니다.
