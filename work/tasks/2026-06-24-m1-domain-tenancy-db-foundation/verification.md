# Verification

## 수행한 검증

### RED 확인

명령:

```powershell
python -m pytest tests/db/test_domain_models.py -q
```

결과: 예상대로 실패했습니다.

```text
ModuleNotFoundError: No module named 'work_schedule_ai.db'
```

### 중간 실패와 조정

초기 모델 구현 후 DB 테스트는 일부 실패했습니다. 실패 원인은 unique/check 검증이 아니라 부모 row와 자식 row를 같은 flush에 넣을 때 SQLite FK insert 순서가 먼저 걸린 것이었습니다. 테스트 목적을 분리하기 위해 부모 row를 먼저 commit하도록 테스트 setup을 정리했습니다.

### DB 테스트 GREEN 확인

명령:

```powershell
python -m pytest tests/db/test_domain_models.py -q
```

결과:

```text
.........                                                                [100%]
9 passed in 0.24s
```

### 전체 테스트

명령:

```powershell
python -m pytest -q
```

결과:

```text
.................                                                        [100%]
17 passed in 0.47s
```

### Diff check

명령:

```powershell
git diff --check
```

결과: whitespace error는 없습니다. Windows line ending 관련 Git warning만 출력됐고 exit code는 0입니다.

## 결과

- SQLAlchemy 2.0 declarative 모델을 추가했습니다.
- 조직, 사용자, 멤버십, 직원, 역할, 직원-역할, 조합 제한 모델을 추가했습니다.
- employee code, role name, employee role, membership, pair constraint 중복 제약을 테스트했습니다.
- pair constraint 정규화 helper와 self-pair 거부를 테스트했습니다.

## 남은 위험

- PostgreSQL RLS와 publication overlap exclusion은 아직 검증하지 않습니다.
- Alembic migration 파일은 아직 없습니다.
- SQLite constraint 동작과 PostgreSQL constraint 동작의 차이는 후속 PostgreSQL integration test에서 확인해야 합니다.
- 자식 테이블 `organization_id`와 부모 employee/role의 organization 일치성은 아직 복합 FK나 trigger로 강제하지 않았습니다. 후속 PostgreSQL migration 단계에서 설계해야 합니다.
