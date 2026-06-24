# First Release Checklist

확인일: 2026-06-24

## 릴리즈 범위

1차 릴리즈 기준은 운영 데모와 초기 파일럿에 필요한 핵심 흐름입니다.

- 지원 규모: 직원 2-50명, 생성 기간 최대 31일
- P0 vertical slice: 조직 생성 -> 직원 4명 -> 휴가 1건 -> 상극 조합 1건 -> 1주 근무표 생성 -> 완화안 승인 -> 재계산 -> 발행 -> 엑셀 다운로드
- 최종 목표 100명 지원과 100명/31일 안정 성능 최적화는 후속 hardening 범위입니다.

## 완료된 기능 기준

- 조직 생성과 기본 `사수`, `부사수` 역할 생성
- 직원 bulk paste upsert/validate
- 휴가/출장/개인 일정 등록
- 상극 조합 등록
- 근무 유형 템플릿과 역할별 필요 인원 설정
- OR-Tools 기반 ScheduleRun 생성
- ScheduleRun 입력 snapshot과 결과 artifact 영속화
- ScheduleIssue, RelaxationProposal, SolverDiagnosticEvent 저장
- 휴가 override 후보가 있는 경우 employee/slot 단위 완화안 제안
- 휴가 후보가 없는 역할 부족은 `mark_manual_review` 제안
- 완화안 승인 기록과 최대 3회 재계산 제한
- 발행된 ScheduleRun 읽기 전용 잠금
- SchedulePublication snapshot 보존과 Excel 다운로드
- manual edit validation API
- LLM 개인정보 익명화, schema validation, fallback explanation
- PostgreSQL RLS migration과 tenant context hook
- Railway API/frontend 배포 자산과 demo seed
- GitHub Actions CI workflow

## 검증 게이트

로컬 기본 게이트:

```powershell
python -m pytest -q
cd frontend
npm run build
```

CI 게이트:

- backend pytest 전체
- PostgreSQL service 기반 RLS integration test
- frontend `npm ci` + `npm run build`

PostgreSQL RLS integration은 `TEST_POSTGRES_URL`이 설정된 환경에서 실행됩니다. 로컬 SQLite 환경에서는 skip됩니다.

## 명시적 후속 범위

- Redis queue 기반 별도 solver worker 완성
- 직원 100명/31일 성능 hardening
- assumption literal 기반 고급 CP-SAT 진단 모델 전체
- 수동 편집 저장 API/UI와 편집 이력 비교
- AuditLog/FairnessLedger/ImportBatch 고도화
- 실제 Railway/운영 PostgreSQL 배포 smoke와 모니터링

## 릴리즈 판정

현재 코드는 1차 릴리즈 후보로 판정합니다. 이유는 P0 흐름과 데이터 불변성, tenant 방어계층, CI 검증 게이트가 코드와 테스트로 고정되어 있기 때문입니다. 후속 범위는 제품 확장성과 운영 hardening 항목으로 분리합니다.
