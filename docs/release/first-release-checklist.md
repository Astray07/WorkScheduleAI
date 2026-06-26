# First Release Checklist

확인일: 2026-06-24

## 릴리즈 범위

1차 릴리즈 기준은 운영 데모와 초기 파일럿에 필요한 핵심 흐름입니다.

- 지원 규모: 직원 2-50명, 생성 기간 최대 31일
- P0 vertical slice: 조직 생성 -> 직원 4명 -> 휴가 1건 -> 상극 조합 1건 -> 1주 근무표 생성 -> 완화안 승인 -> 재계산 -> 발행 -> 엑셀 다운로드
- 직원 100명/31일 저제약 synthetic 회귀 baseline은 포함합니다. 고제약 운영 데이터 안정 성능 최적화는 후속 hardening 범위입니다.

## 완료된 기능 기준

- 조직 생성과 기본 `사수`, `부사수` 역할 생성
- 직원 bulk paste upsert/validate
- 휴가/출장/개인 일정 등록
- 상극 조합 등록
- 근무 유형 템플릿과 역할별 필요 인원 설정
- OR-Tools 기반 ScheduleRun 생성
- Redis queue 기반 별도 worker 실행과 frontend 완료 polling
- worker executor 실패 시 ScheduleRun `failed` terminal 상태 기록
- ScheduleRun 입력 snapshot과 결과 artifact 영속화
- ScheduleIssue, RelaxationProposal, SolverDiagnosticEvent 저장
- 휴가 override 후보가 있는 경우 employee/slot 단위 완화안 제안
- 휴가 후보가 없는 역할 부족은 `mark_manual_review` 제안
- 완화안 승인 기록과 최대 3회 재계산 제한
- 발행된 ScheduleRun 읽기 전용 잠금
- SchedulePublication snapshot 보존과 Excel 다운로드
- manual edit validation/save API와 AuditLog 기록
- 조직 audit log 조회와 CSV export API
- LLM 개인정보 익명화, schema validation, fallback explanation
- PostgreSQL RLS migration과 tenant context hook
- auth enabled 상태에서 trusted upstream 설정이 없으면 조직 스코프 `X-User-Id` 요청 거부
- release gate가 trusted header actor mode를 공개 SaaS ready로 판정하지 않도록 hardening
- signed actor token 기반 `Authorization: Bearer` actor extraction
- 직원 publication scoped signed link 발급과 `Authorization: Bearer` 기반 public 조회/확인 API
- 직원 signed link context의 acknowledgement와 notification records
- RAG 문서 ingest/list/delete API와 citation 필드 계약
- Railway API/frontend 배포 자산과 demo seed
- Railway worker service start command reference
- 운영 metrics/readiness endpoint
- 직원 100명/31일 저제약 synthetic 성능 회귀 baseline
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

Staging 게이트:

- API service, worker service, PostgreSQL, Redis가 분리된 Railway 구성으로 떠 있어야 합니다.
- worker service start command는 `python -m work_schedule_ai.worker.queue_worker`여야 합니다.
- 실제 Redis queue를 통과하는 P0 happy path와 infeasible/relaxation path를 브라우저에서 1회 이상 관통해야 합니다.
- 공개 URL 또는 실사용 파일럿이면 관리자 인증, signed/session actor extraction, 요청 조직 컨텍스트, tenant 접근 제어가 릴리즈 전 필수입니다.
- blocking 컴플라이언스 warning은 현재 warning instance(`warning_code` + 직원 + 슬롯/ISO 주차 + snapshot hash)와 override가 정확히 일치해야 확정 가능합니다.
- 직원 모바일 public 접근은 signed publication link 조회/확인 API 또는 직원 인증을 통해서만 허용합니다. signed link token은 직원 URL query string에 두지 않고 fragment에서 회수해 API `Authorization` header로 전달해야 합니다.

## 명시적 후속 범위

- 직원 100명/31일 고제약 운영 데이터 성능 hardening
- 관리자 회원가입/로그인, 세션 UX, signed actor token 발급/회전 운영 절차
- 직원 모바일 signed link 조회/확인 API를 프론트 화면과 알림 UX에 연결
- RAG embedding/vector index 설계, ingestion UI, 문서 권한 UX, citation 평가셋
- 한국형 warning rule 세분화와 warning override 전용 운영 화면
- demand/budget preview를 solver objective 또는 warning policy로 연결하는 정책 모델
- assumption literal 기반 고급 CP-SAT 진단 모델 전체
- 수동 편집 UI와 편집 이력 비교
- FairnessLedger/ImportBatch 고도화
- 실제 Railway/운영 PostgreSQL 배포 smoke와 모니터링

## 릴리즈 판정

현재 코드는 로컬 통합 후보로 판정합니다. P0 흐름, 데이터 불변성, worker 분리, 수동 편집 저장, 운영 metric은 코드와 테스트로 고정되어 있습니다. 단, 공개 URL 또는 실사용 1차 릴리즈로 판정하려면 인증/요청 조직 컨텍스트와 Railway API+worker+Redis staging P0 수동 검증을 추가로 통과해야 합니다.
