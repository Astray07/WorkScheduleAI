# M1 Publication Excel API Verification

## RED 확인

명령:

```powershell
python -m pytest tests\api\test_schedule_runs_api.py -q
```

결과:

- `4 failed, 14 passed`
- 실패 이유: result payload에 `assignment_snapshot_hash`, `issue_snapshot_hash`가 없어 publication 테스트가 실패했습니다.

명령:

```powershell
python -m pytest tests\db\test_domain_models.py tests\db\test_alembic_migrations.py -q
```

결과:

- `6 failed, 20 passed`
- 실패 이유: `SchedulePublication` 모델과 `schedule_publications` migration/head revision이 없었습니다.

## 집중 GREEN 확인

명령:

```powershell
python -m pytest tests\db\test_domain_models.py tests\db\test_alembic_migrations.py -q
```

결과:

- `26 passed`

명령:

```powershell
python -m pytest tests\api\test_schedule_runs_api.py -q
```

결과:

- `18 passed`

## 남은 검증

없습니다.

## 전체 검증

명령:

```powershell
python -m pytest -q
```

결과:

- `67 passed`

명령:

```powershell
git diff --check
```

결과:

- 종료 코드 0
- CRLF 변환 경고만 출력되었습니다.
