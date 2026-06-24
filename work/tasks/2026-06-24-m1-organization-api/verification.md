# Verification

## 수행한 검증

### RED 확인

명령:

```powershell
python -m pytest tests/api/test_organizations_api.py -q
```

결과: 예상대로 실패했습니다.

```text
ModuleNotFoundError: No module named 'work_schedule_ai.api.dependencies'
```

### API 테스트 GREEN 확인

명령:

```powershell
python -m pytest tests/api/test_organizations_api.py -q
```

결과:

```text
...                                                                      [100%]
3 passed in 0.44s
```

### 전체 테스트

명령:

```powershell
python -m pytest -q
```

결과:

```text
.......................                                                  [100%]
23 passed in 0.79s
```

### Diff check

명령:

```powershell
git diff --check
```

결과: whitespace error는 없습니다. Windows line ending 관련 Git warning만 출력됐고 exit code는 0입니다.

## 결과

- `POST /organizations`를 구현했습니다.
- 조직 생성 시 기본 역할 `사수`, `부사수`를 함께 저장합니다.
- response는 M0 OrganizationResponse 계약에 맞춰 `id`, `name`, `timezone`, `data_version`, `default_roles`를 반환합니다.
- 빈 조직명은 FastAPI/Pydantic validation으로 422를 반환합니다.

## 남은 위험

- 인증과 membership 자동 생성은 아직 없습니다.
- 사용자 1명당 조직 1개 제한은 아직 없습니다.
- 운영 DB session lifecycle과 tenant context 설정은 후속 단계에서 구현해야 합니다.
- 기본 역할 생성 중 일부 실패 시 더 세밀한 오류 매핑은 아직 없습니다.
