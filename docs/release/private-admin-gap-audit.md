# WorkScheduleAI 비공개 관리자용 Gap Audit

작성일: 2026-06-26
브랜치: `feature/m1-scaffold-contract-tests`

## 결론

현재 WorkScheduleAI는 로컬 환경 또는 통제된 스테이징 환경에서 비공개 관리자 검증을 진행할 수 있는 운영 후보 상태입니다.

다만 공개 SaaS 출시 후보는 아닙니다. 공개 URL 노출, 외부 파일럿, 실제 운영 투입 전에는 인증, 요청별 조직 컨텍스트 강제, Redis 워커 경로의 실제 스테이징 검증, 운영 배포 점검이 먼저 필요합니다.

## 구현 완료 범위

### 관리자 기준정보

- 조직 생성과 기본 역할 설정이 구현되어 있습니다.
- 직원과 역할 적격성 관리가 구현되어 있습니다.
- 휴가, 출장, 교육, 개인 일정 등 근무 불가 일정 관리가 구현되어 있습니다.
- 배치 금지, 회피, 선호 관계를 다루는 직원 쌍 제약 관리가 구현되어 있습니다.
- 근무 유형과 역할별 필요 인원 관리가 구현되어 있습니다.
- 스케줄 정책 관리가 구현되어 있습니다.

### 가져오기

- CSV/TSV 미리보기와 적용 기능은 계속 지원됩니다.
- 공식 `.xlsx` 미리보기와 적용 기능이 직원, 근무 불가 일정, 직원 쌍 제약, 정책, 근무 유형에 대해 구현되어 있습니다.
- `.xlsx` 미리보기는 시트, 행 번호, 컬럼, 오류 코드, 메시지를 반환합니다.
- 유효하지 않은 행이 있으면 적용이 차단됩니다.
- 유효한 행은 대상 데이터가 지원하는 경우 natural key 기준 upsert 방식으로 반영됩니다.
- 시트와 컬럼 계약은 `docs/release/import-xlsx-contract.md`에 문서화되어 있습니다.

### 근무표 생성

- OR-Tools가 근무표 생성 엔진으로 유지되어 있습니다.
- LLM은 생성 결정을 내리는 엔진이 아니라 설명 계층으로만 동작하며, 실패 시 fallback 동작을 갖습니다.
- 근무표 기간은 1일부터 31일까지 지원됩니다.
- 시나리오에서 생성된 근무 유형 동기화는 요일 적용 범위를 존중하며, 평일 야간만 있는 경우 주말 슬롯을 만들지 않습니다.
- 채우지 못한 필요 인원은 solver 실패가 아니라 `ScheduleIssue`로 노출되는 soft penalty입니다.
- 재계산은 승인된 override와 수동 잠금을 보존하며, `recalculation_count`는 최대 3회로 제한됩니다.
- `current_attempt_no`는 워커의 기술적 재시도 상태로 남아 있으며, 관리자의 재계산 횟수와 분리되어 있습니다.

### Solver 강화

- 50명, 31일 기준 deterministic 회귀 테스트가 기본 테스트에 포함되어 있습니다.
- 100명, 31일 기준 고제약 benchmark는 명시적 환경 변수 opt-in 뒤에 실행되도록 구성되어 있습니다.
- 고제약 benchmark는 역할 적격성, 근무 불가 슬롯, 금지 쌍, 주간 상한, 최대 연속 근무, 최소 휴식, 주말 상한, 야간 상한, 필요 인원 수, 예상되는 soft unfilled issue 동작을 확인합니다.

### 검토와 운영 UI

- 운영자 콘솔은 시나리오 설정, 기준정보 관리, 정책 편집, 가져오기 미리보기와 적용, 근무표 생성, 수동 배정 편집, 검증, 감사 내역 확인, 재계산, 확정, Excel 다운로드를 지원합니다.
- 현재 실행 결과의 fairness 요약은 장기 fairness와 분리되어 표시됩니다.
- 근무표 실행 이력 비교는 배정, 수동 잠금, issue, fairness delta를 대상으로 구현되어 있습니다.
- 장기 fairness 대시보드는 확정본 또는 실행 결과를 기준으로 기간 필터, 배정 수, 야간 수, 주말 수, 역할별 수, 평균 delta를 표시합니다.
- 운영 확장 패널의 직원 요청 queue는 승인 대기 상태만 최대 5건 표시합니다.
- 운영 지표와 readiness endpoint가 로컬 및 스테이징 점검용으로 존재합니다.
- PostgreSQL tenant context hook은 존재하지만, 공개 인증과 멤버십 강제는 아직 release gate입니다.
- `WORKSCHEDULEAI_AUTH_REQUIRED=1`일 때 조직 스코프 API는 `WORKSCHEDULEAI_TRUSTED_UPSTREAM_AUTH=1` 없이는 `X-User-Id`를 받지 않도록 fail-closed 처리합니다.
- `WORKSCHEDULEAI_SIGNED_ACTOR_SECRET`이 설정되면 조직 스코프 API는 `Authorization: Bearer <signed actor token>`을 검증해 actor를 추출할 수 있습니다.
- release gate는 trusted upstream header mode를 공개 SaaS ready로 보지 않으며, signed actor token mode와 구분합니다.

### RAG와 근거 제시

- RAG API는 tenant-scoped 문서 chunk와 query audit만 저장합니다.
- RAG 문서는 tenant-scoped 목록 조회와 관리자 삭제 API로 관리할 수 있으며, viewer는 목록 조회만 가능하고 employee/member는 문서 관리 API에서 거부됩니다.
- RAG query는 `SchedulePolicy` 또는 `ScheduleRun`을 직접 생성하거나 수정하지 않는 guardrail 테스트로 고정되어 있습니다.
- 현재 retrieval은 keyword 기반이며 문서 제목과 chunk 본문을 함께 점수화합니다. evidence citation은 문서 ID, chunk ID, 제목, 출처 유형, checked_at, confidence를 포함합니다. embedding/vector index와 평가셋은 후속 품질 고도화 범위입니다.

### 수요와 비용 Preview

- demand driver와 labor budget은 solver objective를 직접 바꾸지 않고 preview API에서 staffing/cost gap을 보여주는 단계입니다.
- preview는 under/over/matched staffing 상태, staffing variance, planned labor cost, budget variance, no/within/over budget 상태를 반환합니다.
- over/under staffing penalty나 hard budget constraint를 solver objective로 반영하는 작업은 정책 모델과 테스트를 더 고정한 뒤 진행합니다.

### 확정과 감사성

- `ScheduleRun`과 `SchedulePublication`은 분리되어 있습니다.
- 확정본은 변경 불가능한 결과 snapshot을 저장합니다.
- 확정본 Excel export는 저장된 snapshot을 기준으로 생성됩니다.
- 수동 배정 저장과 확정본 생성은 audit log를 남깁니다.
- 조직 audit log는 UI 조회와 CSV export API를 지원하며 tenant scope와 관리자 권한으로 제한됩니다.
- 컴플라이언스 경고는 법률 자동 판단이 아니라 운영 검토용 warning입니다.
- blocking warning override는 `warning_code`, 직원, 슬롯 또는 ISO 주차, 현재 warning snapshot hash가 일치해야 확정 시 인정됩니다.
- warning override 사유와 actor는 audit log에 기록됩니다.

### 직원 모바일 접근

- 관리자는 확정본과 직원에 묶인 HMAC signed publication link를 발급할 수 있습니다.
- signed link token은 조직, publication, 직원, 만료 시각을 포함하며 변조, 만료, 다른 직원 재사용을 거부하는 테스트가 있습니다.
- 생성된 직원 URL은 token을 query string이 아니라 URL fragment에 담고, public API는 `Authorization: Bearer <employee-link-token>`으로 직원 본인의 확정 근무표 context 조회와 acknowledgement 기록을 허용합니다.
- archived publication은 signed link public API에서 조회와 acknowledgement가 차단됩니다.
- 아직 직원 모바일 화면과 변경 알림 UX는 signed link public API에 연결되지 않았습니다. 화면 연결 전에는 직원용 공개 접근을 제품 기능으로 안내하지 않아야 합니다.

## 비공개 관리자판에서 의도적으로 제외한 범위

### 일반 사용자 휴가 또는 일정 요청

상태: 제외.

이유: 현재 운영 후보는 관리자가 직접 입력하거나 가져온 데이터를 기준으로 동작합니다. 일반 사용자 요청 흐름에는 사용자 식별, 직원-사용자 연결, 요청 상태 머신, 승인 대기열, 알림 동작이 필요합니다.

리스크: 관리자가 요청을 직접 입력하거나 파일로 가져와야 합니다. 통제된 비공개 검증에서는 허용 가능하지만, 직원 self-service rollout에는 부족합니다.

### 조직 초대와 다중 사용자 온보딩

상태: 제외.

이유: 비공개 관리자 운영은 신뢰된 운영자 컨텍스트를 전제로 합니다. 초대 기능에는 계정 생명주기, 멤버십 권한, 이메일 발송, 오남용 방지가 필요합니다.

리스크: 여러 실제 관리자가 안전하게 self-service로 접근할 수 없습니다. 공개 또는 다중 관리자 스테이징 전에는 인증과 멤버십 강제를 먼저 구현해야 합니다.

### 알림

상태: 제외.

이유: 현재 제품은 override 승인에 알림이 필요하다는 정보는 기록하지만, 이메일, Slack, 인앱 알림을 발송하지 않습니다.

리스크: 커뮤니케이션은 수동으로 처리해야 합니다. 비공개 운영자 검증에는 허용 가능하지만, 자율적인 업무 흐름 도입에는 부족합니다.

### 공개 회원가입

상태: 제외.

이유: 공개 회원가입은 위협 모델을 바꿉니다. 인증, 모든 endpoint의 tenant isolation 강제, rate limit, 이메일 검증, 계정 복구, 오남용 대응이 필요합니다.

리스크: 이 범위가 구현되고 검증되기 전까지 앱을 공개 self-service SaaS로 노출하면 안 됩니다.

### 결제

상태: 제외.

이유: 과금은 비공개 운영 검증 경로 밖에 있으며, 계정, 구독, 세금, 송장, entitlement 복잡도를 추가합니다.

리스크: 아직 상업적 self-service 출시 경로는 없습니다.

### 외부 HR 연동

상태: 제외.

이유: 비공개 검증에는 `.xlsx`와 수동 기준정보 API가 충분합니다. 외부 HR 동기화에는 매핑, 인증 정보 저장, 충돌 처리, 감사 의미론, 데이터 보호 검토가 필요합니다.

리스크: 데이터 최신성은 관리자 가져오기 또는 수동 수정에 의존합니다.

### 급여, 근태, 법률 자동 판단

상태: 제외.

이유: 현재 solver는 설정된 스케줄 제약을 집행합니다. 법률, 급여, 컴플라이언스 판단을 자동으로 내리지는 않습니다.

리스크: 운영자는 결과를 지역 노동 규칙과 내부 정책에 맞게 별도로 검토해야 합니다.

## 남은 출시 리스크

- 인증과 tenant 접근 제어는 공개 URL 또는 실제 외부 파일럿의 release gate입니다. signed actor token 추출은 추가되었지만, 관리자 회원가입/로그인, 세션 UX, 키 관리와 운영 배포 검증은 남아 있습니다.
- 직원 모바일 화면은 signed link 기반 조회/확인 API와 변경 알림 UX에 연결해야 합니다.
- production-ready라고 부르기 전 Railway/API/worker/PostgreSQL/Redis 스테이징 검증이 필요합니다.
- 100명, 31일 기준 강화 benchmark는 opt-in이며 기본 CI runtime gate가 아닙니다.
- 한국형 warning rule 세분화와 override 전용 운영 화면은 남은 제품화 작업입니다.
- 확정본 snapshot 기반 장기 fairness는 요청 시 JSON을 파싱합니다. 비공개 검증에는 충분하지만, 이력이 커지면 aggregate table 또는 materialized summary가 필요할 수 있습니다.
- 장기 fairness는 현재 active employee를 행 기준으로 사용합니다. 따라서 나중에 직원이 비활성화되면 과거 리포트의 행 구성이 바뀔 수 있습니다.
- 브라우저 smoke test는 UI 렌더링 확인이 목적일 때 mocked API를 사용했습니다. 실제 Redis-backed end-to-end 스테이징 smoke는 별도로 남아 있습니다.
- 현재 release posture는 공개 서비스 출시가 아니라 비공개 관리자 검증을 위한 로컬 통합 후보로 표현해야 합니다.

## 제가 보는 현재 남은 일

1. 인증, 멤버십, tenant 접근 제어를 먼저 구현하고 endpoint별 권한 테스트를 계속 추가해야 합니다. 정책, 가져오기, 기준정보 mutation의 저권한 거부 테스트는 추가되었지만 전체 endpoint matrix는 아직 후속 hardening 범위입니다.
2. Railway 스테이징에서 API, worker, PostgreSQL, Redis, frontend를 실제로 연결한 end-to-end smoke를 실행해야 합니다.
3. 운영 보안과 관측성을 보강해야 합니다. audit log 조회/export와 readiness/metrics는 존재하지만, 장애 시 worker 재시도와 실패 추적 기준은 더 정리해야 합니다.
4. 장기 fairness 데이터가 커질 경우를 대비해 확정본 snapshot JSON 파싱 방식의 한계를 측정하고, 필요하면 aggregate table로 전환해야 합니다.
5. 일반 사용자 요청, 조직 초대, 알림은 공개 또는 다중 사용자 파일럿 전에 구현해야 합니다. 비공개 단일 관리자 검증만 계속한다면 후순위로 둘 수 있습니다.
6. 제품 운영 문서를 정리해야 합니다. 스테이징 배포 절차, seed data, rollback, 백업, 장애 대응 체크리스트가 필요합니다.
7. 운영자 UX는 `.xlsx` 템플릿 다운로드, import 오류 안내, 장기 fairness 필터, 확정본 리포트 export를 중심으로 다듬는 것이 좋습니다.

## 검증 근거

직전 기능 완성 게이트에서 다음 검증을 통과한 상태입니다.

- `python -m pytest -q`: 186 passed, 2 skipped
- 전체 `frontend/src/*.test.mjs`
- `npm run build`
- `git diff --check`
- `git rev-list --left-right --count "HEAD...@{u}"`

이번 hardening에서는 trusted upstream auth gate와 대표 RBAC deny 테스트를 추가했으며, 공개 SaaS readiness는 여전히 false로 유지합니다.

## 관련 커밋

- `da47e98 feat: add xlsx import preview`
- `2af69c2 test: add high constraint solver benchmark`
- `1ea0227 feat: add schedule run comparison`
- `2afae9d feat: add long term fairness dashboard`
- `c54ceee docs: add private admin gap audit`
