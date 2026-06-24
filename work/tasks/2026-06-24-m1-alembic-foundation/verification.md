# Verification

## 수행한 검증

### RED 확인

명령:

```powershell
python -m pytest tests/db/test_alembic_migrations.py -q
```

결과: 예상대로 실패했습니다.

```text
alembic.util.exc.CommandError: No 'script_location' key found in configuration.
```

### 중간 경고 정리

초기 Alembic 설정 후 migration 테스트는 통과했지만 다음 경고가 있었습니다.

```text
DeprecationWarning: No path_separator found in configuration
```

`alembic.ini`에 `path_separator = os`를 추가해 경고를 제거했습니다.

### Migration 테스트 GREEN 확인

명령:

```powershell
python -m pytest tests/db/test_alembic_migrations.py -q
```

결과:

```text
...                                                                      [100%]
3 passed in 0.46s
```

### 전체 테스트

명령:

```powershell
python -m pytest -q
```

결과:

```text
....................                                                     [100%]
20 passed in 0.72s
```

### Diff check

명령:

```powershell
git diff --check
```

결과: 출력 없음, exit code 0입니다.

## 결과

- Alembic 설정 파일과 env를 추가했습니다.
- `work_schedule_ai.db.models.Base.metadata`를 migration target metadata로 연결했습니다.
- 첫 revision `20260624_0001`을 추가했습니다.
- SQLite 임시 DB에서 `upgrade head`가 M1 foundation 테이블과 핵심 constraint를 만드는지 검증했습니다.

## 남은 위험

- SQLite migration 테스트는 PostgreSQL RLS와 exclusion constraint를 검증하지 못합니다.
- PostgreSQL 환경에서 `btree_gist` extension 사용 가능 여부는 아직 확인하지 않았습니다.
- 첫 revision은 현재 M1 foundation 테이블만 포함합니다. ScheduleRun, SchedulePublication, ShiftSlot 등은 후속 모델/migration 작업이 필요합니다.
