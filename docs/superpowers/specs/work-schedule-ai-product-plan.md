# WorkScheduleAI 기획서

> 상태: 초안  
> 기준 접근안: OR-Tools 기반 제약 최적화 엔진 + LLM 설명/추천 보조  
> 레퍼런스 확인일: 2026-06-24

## 1. 배경

WorkScheduleAI는 여러 회사가 각자의 근무 방식에 맞춰 근무표를 생성하고 관리할 수 있는 SaaS형 근무표 작성 서비스입니다. 기본 근무 형태는 `사수 1명 + 부사수 1명`이지만, 회사별로 역할명, 역할별 필요 인원, 근무 시간대, 근무 템플릿, 제약 정책을 설정할 수 있어야 합니다.

이 서비스의 핵심 문제는 단순한 표 자동 채우기가 아니라, 휴가, 출장, 개인 일정, 역할 자격, 직원 간 조합 제한, 근무량 공정성 등 현실의 제약을 반영해 가능한 근무표를 찾고, 불가능한 경우에는 관리자가 조율할 수 있는 최소 손실 후보를 제시하는 것입니다.

## 2. 제품 목표

1. 2명부터 100명까지의 인원 규모를 지원합니다.
2. 여러 조직이 독립적으로 사용할 수 있는 SaaS 구조를 갖춥니다.
3. 회사별 직원, 역할, 근무 유형, 휴가/출장/개인 일정, 조합 제한을 저장합니다.
4. 화면 입력과 엑셀 업로드/다운로드를 모두 지원합니다.
5. 제약을 최대한 지키면서 근무표를 자동 생성합니다.
6. 해가 나오지 않으면 시스템이 제약을 임의로 깨지 않고, 관리자에게 최소 손실 완화안을 추천합니다.
7. LLM은 근무표를 직접 생성하지 않고, 충돌 원인 설명과 추천안 요약을 담당합니다.
8. LLM에 전달되는 데이터는 반드시 요청 단위로 익명화합니다.
9. 최종 서비스는 Railway 배포를 목표로 합니다.

## 3. 비목표

초기 완성 범위에서 다음은 제외합니다.

- 급여 계산
- 근태 기록기 연동
- 법정 근로시간 자동 판정의 완전한 법률 보증
- 결제/요금제/구독 관리
- 외부 HR 시스템과의 실시간 연동
- 모바일 앱
- 실시간 공동 편집

다만 데이터 구조는 향후 확장을 막지 않는 방향으로 설계합니다.

## 4. 범위 단계

초기 기획은 완성본처럼 보이는 흐름을 목표로 하되, 구현 범위가 한 번에 커지지 않도록 MVP, v1, v2를 분리합니다. 실제 구현 착수 기준은 아래 `4.1 1차 완성 범위` 표를 단일 기준으로 삼습니다.

| 단계 | 포함 기능 | 제외하거나 뒤로 미루는 기능 |
| --- | --- | --- |
| MVP | 조직 관리자 전용, 조직 생성, 직원/역할 관리, 근무 유형 템플릿, 휴가/출장/개인 일정 등록, 조합 제한 등록, 근무표 생성, 서버 생성 완화안, 예외 승인 기록, 엑셀 다운로드, Railway 배포 | 일반 사용자 휴가 신청, 정식 엑셀 업로드, 고급 정책 UI, 결제 |
| v1 | 엑셀 업로드, LLM 설명 고도화, 고급 정책 설정, 예외 승인 후 재계산 고도화, 생성 이력 비교, 일반 사용자 조회 | 승인 워크플로우 자동화, 외부 시스템 연동 |
| v2 | 일반 사용자 휴가/일정 요청, 조직 초대, 감사 로그 고도화, 알림, 과거 근무표 기반 장기 공정성 대시보드 | 급여/근태/법률 자동 판정 |

MVP에서도 데이터 모델은 멀티테넌트와 확장 가능한 제약 구조를 전제로 둡니다. 단, 모든 화면과 운영 기능을 한 번에 구현하지 않습니다.

1차 완성 범위에서 제외하는 v1 기능은 엑셀 업로드, 고급 정책 UI, 생성 이력 비교, 일반 사용자 조회입니다. 이 기능들은 데이터 구조만 막지 않고 후속 단계로 둡니다.

### 4.1 1차 완성 범위

아래 표가 구현 착수 기준의 우선 범위입니다. 위 MVP/v1/v2 표보다 이 표를 먼저 따릅니다.

| 구분 | 포함 | 제외 | 데이터 모델만 준비 |
| --- | --- | --- | --- |
| 조직/권한 | 관리자 회원가입, 조직 생성, 관리자 단일 조직 사용 | 일반 사용자 계정, 조직 초대 | Membership, EmployeeUserLink |
| 기준 정보 | 직원/역할/근무 유형/휴가/조합 제한 CRUD, 직원 bulk paste 입력 | 전체 엑셀 업로드 검증 미리보기 | ImportBatch |
| 스케줄 생성 | P0 데모 1주 생성, 1차 UI/API 최대 31일 생성, 기본 사수/부사수 템플릿, 커스텀 역할/필요 인원 | 31일 초과 대형 생성, 고급 반복 규칙 편집 | ScheduleInputSnapshot |
| 제약/완화안 | 절대 불가/승인 완화/soft penalty 적용, 단일 완화안 승인 후 재계산 | 묶음 완화안 승인 UI, 다중 승인 워크플로우 | group_id, requires_proposal_ids |
| 결과 검토 | 결과 그리드, ScheduleIssue 목록, 추천 완화안 카드, 수동 수정 후 재검증, 최소 SchedulePublication 생성/잠금 | 드래그 앤 드롭 편집, 생성 이력 비교 | publication 고도화 |
| AI 설명 | 서버 구조화 데이터 기반 LLM 설명, 실패 시 템플릿 fallback | LLM 기반 정책 추천, 자연어 명령 입력 | LLM eval dataset 구조 |
| 입출력 | 확정 근무표 엑셀 다운로드 | 정식 엑셀 업로드 | ImportBatch |
| 배포 | Railway API/worker/PostgreSQL/Redis 배포 | 운영 모니터링 고도화, 결제 | AuditLog |

1차 tenant UX:

- 가입 사용자는 1차 릴리즈에서 조직 1개만 생성하고 관리합니다.
- organization switcher와 다중 조직 전환 UI는 만들지 않습니다.
- 도메인 모델은 다중 조직을 지원하지만, 화면 흐름은 단일 조직 기준으로 단순화합니다.

### 4.2 P0 Vertical Slice

첫 구현은 넓은 기능보다 한 번 관통되는 얇은 흐름을 우선합니다.

Happy path:

1. 관리자가 가입하고 조직을 생성합니다.
2. 기본 역할 `사수`, `부사수`가 생성됩니다.
3. 직원 4명을 bulk paste 또는 화면 입력으로 등록합니다.
4. 1주일짜리 하루 1근무 템플릿을 생성합니다.
5. 휴가 1건과 상극 조합 1건을 등록합니다.
6. 근무표 생성을 요청합니다.
7. worker가 ScheduleRun을 처리하고 결과 그리드를 반환합니다.
8. 관리자가 결과를 확정합니다.
9. 엑셀로 다운로드합니다.

Infeasible or issue path:

1. 휴가와 조합 제한 때문에 특정 슬롯의 부사수가 미배정됩니다.
2. ScheduleIssue가 생성됩니다.
3. 서버가 단일 완화안을 추천합니다.
4. LLM 설명이 가능하면 표시하고, 실패하면 서버 fallback 문구를 표시합니다.
5. 관리자가 단일 완화안을 승인합니다.
6. 재계산 후 미배정이 해소되거나 남은 이유를 표시합니다.

### 4.3 1차 릴리즈 제한

- 권장 직원 수: 2-50명
- 최대 지원 직원 수: 100명까지 데이터 입력은 가능하지만, 1차 릴리즈 성능 보장은 50명 기준입니다.
- 최종 목표는 100명 규모 안정 지원이며, 100명/31일 성능 최적화는 후속 hardening 범위로 둡니다.
- P0 데모와 solver golden path의 기본 생성 기간: 1주
- 1차 릴리즈 UI/API의 최대 생성 기간: 31일
- 기본 solver timeout: 30초
- 최대 solver timeout: 120초
- 기본 `proposal_top_n`: 3개
- 지원 반복 규칙: 하루 1근무, 오전/오후/야간, 당직/비상근무 템플릿
- 미지원: 법적 준수 자동 보증, 급여 계산, 실시간 공동 편집, 외부 HR 연동

### 4.4 Milestones And Exit Criteria

| 마일스톤 | 목표 | Exit criteria |
| --- | --- | --- |
| M0 계약 고정 | OpenAPI 초안, ScheduleRun 상태 머신, 핵심 DB invariant 확정 | 프론트가 mock API로 결과 화면을 만들 수 있습니다. |
| M1 도메인/테넌시 | 조직, 직원, 역할, 근무 유형, 불가 일정, 조합 제한 CRUD | tenant 격리 테스트와 주요 unique constraint 테스트가 통과합니다. |
| M2 Solver MVP | 4명/1주 golden case, 휴가/상극/미배정 케이스 | deterministic solver 테스트가 CI에서 통과합니다. |
| M3 ScheduleRun worker | API enqueue, worker 실행, 상태 조회, cancel/retry | 중복 요청이 같은 ScheduleRun으로 수렴합니다. |
| M4 결과/예외 UI | 결과 그리드, ScheduleIssue, 단일 RelaxationProposal 승인 | happy path와 issue path를 브라우저에서 시연할 수 있습니다. |
| M5 LLM 설명 | 구조화 출력, fallback, 개인정보 누출 테스트 | LLM 실패 시에도 결과 화면이 정상 동작합니다. |
| M6 배포/제출 | Railway 배포, 엑셀 다운로드, 데모 데이터 | P0 vertical slice를 배포 URL에서 시연할 수 있습니다. |

주요 개발 트랙:

- Solver/진단/완화안: 가장 높은 기술 리스크입니다.
- 테넌시/CRUD/API: 프론트와 worker가 의존하는 기반입니다.
- 결과 그리드/승인 UX: 사용자 가치가 드러나는 핵심 화면입니다.
- LLM 설명: 기능 완성의 부가 레이어이며, solver 결과 표시를 막지 않습니다.

Railway 데모 데이터:

- 직원 4명
- 1주 근무표
- 휴가 1건
- 상극 조합 1건
- 미배정 또는 완화안이 발생하는 케이스 1건
- 확정된 SchedulePublication 1건

## 5. 사용자와 권한

### 조직 관리자

- 조직 설정을 관리합니다.
- 직원, 역할, 근무 유형, 제약 정책을 관리합니다.
- 근무표를 생성하고 예외 승인 여부를 결정합니다.
- 최종 근무표를 저장하고 내보냅니다.

### 일반 사용자

- v1 이후 본인의 근무표를 조회합니다.
- v2 이후 본인의 휴가, 출장, 개인 일정을 입력하거나 요청합니다.
- 직원이 서비스에 로그인하지 않는 조직도 지원합니다.

### 시스템 관리자

- 서비스 운영을 위한 전체 시스템 상태를 관리합니다.
- 개별 조직의 민감한 근무 데이터에는 원칙적으로 접근하지 않는 구조를 지향합니다.
- 기술적으로는 PostgreSQL Row Level Security(RLS)와 애플리케이션 레벨 조직 스코프 검사를 함께 사용해 tenant 격리를 강제합니다.

## 6. 핵심 사용자 흐름

### 6.1 조직 초기 설정

1. 사용자가 회원가입 또는 로그인합니다.
2. 조직을 생성합니다.
3. 기본 템플릿을 선택합니다.
   - 하루 1근무
   - 오전/오후/야간 근무
   - 당직/비상근무
   - 직접 설정
4. 기본 역할은 `사수 1명 + 부사수 1명`으로 생성됩니다.
5. 필요하면 역할명과 역할별 필요 인원을 수정합니다.

### 6.2 기준 정보 등록

1. 직원 목록을 화면에서 입력합니다.
2. 직원별 역할 가능 여부를 지정합니다.
3. 휴가, 출장, 교육, 개인 일정 등 근무 불가 일정을 등록합니다.
4. 직원 간 조합 제한을 등록합니다.
   - 절대 같이 근무 금지
   - 승인 시 1회 완화 가능
   - 가능하면 회피
   - 가능하면 선호
5. v1 이후 조직별 고급 설정에서 제약 가중치를 수정할 수 있습니다.

### 6.3 근무표 생성

1. 관리자가 생성 기간을 선택합니다.
2. 근무 유형 또는 템플릿에 따라 근무 슬롯을 생성합니다.
3. 시스템이 데이터 유효성을 검사합니다.
4. 최적화 엔진이 1차로 절대 불가 제약과 승인 필요 제약을 모두 지키는 근무표를 찾습니다.
5. 성공하면 근무표와 품질 점수를 보여줍니다.
6. 실패하거나 미배정 이슈가 남으면 서버가 구조화된 충돌 원인과 최소 손실 완화안을 생성합니다.
7. 1차에서는 비동기 LLM 설명을 시도하고, 실패하면 서버 fallback 문구를 표시합니다. v1에서는 설명 품질과 eval 범위를 고도화합니다.

### 6.4 예외 검토와 승인

1. 관리자는 추천 완화안을 확인합니다.
2. 예외 승인, 조합 제한 완화, 미배정 유지, 수동 조정 중 하나를 선택합니다.
3. 승인된 예외는 기록으로 남깁니다.
4. 시스템은 승인 내용을 반영해 근무표를 다시 생성하거나 수정합니다.

### 6.5 최종 저장과 내보내기

1. 관리자는 생성된 근무표를 검토합니다.
2. 필요하면 직접 수정합니다.
3. 최종 근무표를 확정하고 잠급니다.
4. 확정된 근무표는 입력 스냅샷과 함께 보존합니다.
5. 엑셀 다운로드 또는 화면 공유용 보기로 내보냅니다.

## 7. 도메인 모델

### Organization

조직 단위입니다. 모든 주요 데이터는 `organization_id`로 분리합니다.

주요 필드:

- id
- name
- timezone
- default_schedule_policy_id
- data_version
- created_at

### User

로그인 사용자입니다.

주요 필드:

- id
- email
- name
- password_hash 또는 외부 인증 id
- created_at

### Membership

사용자와 조직의 관계입니다.

주요 필드:

- organization_id
- user_id
- role: admin, member
- created_at

### Employee

근무표에 배정되는 직원입니다. 사용 계정과 직원 정보는 분리합니다. 직원이 서비스에 로그인하지 않을 수도 있기 때문입니다.

주요 필드:

- id
- organization_id
- name
- employee_code
- active
- seniority_level
- max_shifts_per_week
- max_shifts_per_month
- notes

`employee_code`는 엑셀 업로드 시 자연키로 사용합니다. 재업로드 기본 동작은 `employee_code` 기준 upsert이며, 전체 replace는 별도 확인을 받은 경우에만 수행합니다.

### EmployeeUserLink

로그인 사용자와 직원 정보를 연결합니다. 일반 사용자 기능이 없는 MVP에서는 선택 사항입니다.

주요 필드:

- organization_id
- employee_id
- user_id
- status: invited, linked, disabled

### Role

근무 슬롯에서 요구하는 역할입니다.

기본값:

- 사수
- 부사수

확장 예:

- 책임자
- 보조
- 야간 담당

주요 필드:

- id
- organization_id
- name
- description

### EmployeeRole

직원이 어떤 역할을 맡을 수 있는지 나타냅니다.

주요 필드:

- organization_id
- employee_id
- role_id
- priority
- active

### ShiftType

회사가 정의하는 근무 유형입니다.

예:

- 평일 근무
- 야간 근무
- 주말 당직
- 비상 대기

주요 필드:

- id
- organization_id
- name
- local_start_time
- local_end_time
- crosses_midnight
- timezone
- recurrence_rule
- recurrence_exceptions
- holiday_policy
- active

반복 규칙은 RFC 5545의 RRULE 개념을 참고하되, 초기 구현에서는 일/주/월 단위의 제한된 프리셋부터 지원합니다.

### ShiftRequirement

근무 유형별로 필요한 역할과 인원 수입니다.

예:

- 야간 근무: 사수 1명, 부사수 1명
- 비상 대기: 책임자 1명, 보조 2명

주요 필드:

- id
- organization_id
- shift_type_id
- role_id
- required_count
- unfilled_weight_override

### ShiftSlot

특정 날짜와 시간에 실제로 생성된 근무 슬롯입니다.

주요 필드:

- id
- organization_id
- shift_type_id
- starts_at
- ends_at
- local_date
- timezone
- status

`starts_at`과 `ends_at`은 timezone이 반영된 실제 timestamp로 저장합니다. 22:00-06:00처럼 자정을 넘기는 근무는 `crosses_midnight` 규칙으로 다음 날짜 종료 시각을 계산합니다.

### Assignment

특정 슬롯의 특정 역할에 배정된 직원입니다.

주요 필드:

- id
- organization_id
- schedule_run_id
- shift_slot_id
- role_id
- employee_id
- source: solver, manual, override
- locked_by_user
- attempt_no
- created_at

`Assignment`는 실제 직원이 배정된 경우만 표현합니다. 미배정, 인원 축소, 수동 조정 필요 같은 문제는 `ScheduleIssue`로 별도 저장합니다.

### ScheduleIssue

근무표 생성 결과에서 배정으로 표현할 수 없는 문제를 저장합니다.

주요 필드:

- id
- organization_id
- schedule_run_id
- shift_slot_id
- role_id
- type: unfilled_requirement, reduced_requirement, manual_review_required
- missing_count
- severity
- reason_code
- metadata_json
- attempt_no
- created_at

### Unavailability

휴가, 출장, 교육, 개인 일정 등 근무 불가 일정입니다.

주요 필드:

- id
- organization_id
- employee_id
- type: vacation, business_trip, training, personal
- starts_at
- ends_at
- override_allowed
- note

불가 일정은 날짜 단위와 시간 단위를 모두 표현할 수 있어야 합니다. 슬롯과의 겹침 판정은 `starts_at < slot.ends_at AND ends_at > slot.starts_at` 기준으로 처리합니다.

### PairConstraint

직원 간 조합 제약입니다.

주요 필드:

- id
- organization_id
- employee_a_id
- employee_b_id
- type: blocked, avoid, prefer
- severity
- override_allowed
- active

기본 정책:

- `blocked`는 기본적으로 승인 필요 제약입니다.
- 1차 생성에서는 절대 지키지만, 미배정 손실을 줄일 수 있을 때 관리자에게 완화 후보로 제시할 수 있습니다.
- 자동으로 깨지는 제약이 아닙니다.

### SchedulePolicy

조직별 제약 가중치와 운영 제한 설정입니다.

주요 필드:

- id
- organization_id
- name
- min_rest_hours
- max_consecutive_shifts
- max_shifts_per_week
- max_shifts_per_month
- deterministic_mode
- default_random_seed
- solver_timeout_seconds
- proposal_top_n
- default_unfilled_requirement_weight
- weight_business_trip_override
- weight_vacation_override
- weight_pair_block_override
- weight_personal_schedule_override
- weight_min_rest_violation
- weight_consecutive_shift_violation
- weight_workload_imbalance
- weight_preference_violation
- weight_pair_avoid_violation
- weight_pair_prefer_reward

### SchedulePolicyRoleWeight

커스텀 역할별 미배정 손실 점수를 저장합니다. 기본 `사수/부사수` 역할은 조직 생성 시 기본값을 시드합니다.

주요 필드:

- id
- organization_id
- schedule_policy_id
- role_id
- unfilled_weight

역할별 값이 없으면 `SchedulePolicy.default_unfilled_requirement_weight`를 사용하고, 특정 근무 요구사항이 더 중요하면 `ShiftRequirement.unfilled_weight_override`가 우선합니다.

### ScheduleRun

근무표 생성 실행 기록입니다. 재현성과 감사 추적을 위해 입력과 실행 설정을 함께 저장합니다.

주요 필드:

- id
- organization_id
- period_start
- period_end
- status: queued, running, succeeded, infeasible, failed, canceled
- solver_status
- solution_quality: optimal, feasible_not_proven_optimal, infeasible, unknown
- hard_score
- approvable_score
- soft_score
- objective_score_breakdown
- input_snapshot_id
- input_snapshot_hash
- organization_data_version
- schedule_model_version
- ortools_version
- solver_parameter_json
- random_seed
- num_search_workers
- timeout_seconds
- current_attempt_no
- recalculation_count
- created_by
- created_at
- started_at
- finished_at
- canceled_at

동일 입력 재현을 목표로 할 때는 `random_seed`를 고정하고 `num_search_workers=1`을 사용합니다. 다만 이 설정은 성능을 낮출 수 있으므로, 빠른 생성 모드와 재현성 우선 모드를 분리합니다.

`current_attempt_no`는 worker의 기술적 실행/재시도 횟수입니다. `recalculation_count`는 관리자 승인 또는 수동 변경 후 재계산 라운드 수이며, 1차 릴리즈의 3회 한도는 `recalculation_count`에만 적용합니다.

### ScheduleInputSnapshot

생성 요청 시점의 입력 데이터를 보존합니다. ScheduleRun row가 지나치게 커지지 않도록 snapshot payload는 별도 테이블 또는 오브젝트 저장소로 분리할 수 있습니다.

주요 필드:

- id
- organization_id
- snapshot_hash
- payload_json
- storage_uri
- created_at

초기 구현에서는 `payload_json`을 사용할 수 있고, 데이터가 커지면 `storage_uri` 기반 저장으로 이전합니다.

재현성을 위해 snapshot에는 원시 입력뿐 아니라 생성된 ShiftSlot 목록과 ShiftRequirement 목록도 포함합니다. 반복 규칙, timezone, DST 처리 결과가 나중에 달라져도 같은 snapshot으로 동일한 solver 입력을 재구성할 수 있어야 합니다.

### SchedulePublication

관리자가 최종 확정한 근무표입니다. 실행 기록인 `ScheduleRun`과 발행 상태를 분리합니다.

주요 필드:

- id
- organization_id
- schedule_run_id
- period_start
- period_end
- status: published, archived
- assignment_snapshot_hash
- issue_snapshot_hash
- published_by
- published_at
- locked_at

같은 조직의 같은 기간에는 기본적으로 하나의 active publication만 허용합니다.

1차 릴리즈에서는 같은 조직의 active publication 기간이 일부라도 겹치면 새 publication을 막습니다. 겹침 기준은 `new.period_start < existing.period_end AND new.period_end > existing.period_start`입니다. 부분 겹침 허용, archive/split 동작은 v1 이후로 둡니다.

발행된 ScheduleRun의 Assignment와 ScheduleIssue는 수정할 수 없습니다. 발행 이후 변경이 필요하면 기존 publication을 archive하고 새 ScheduleRun을 생성해 다시 발행합니다.

### RelaxationProposal

미배정 손실이 높거나 승인 필요 제약 때문에 품질이 낮을 때 제시되는 완화안입니다. 원본 후보는 LLM이 아니라 서버가 구조화된 규칙으로 생성합니다.

주요 필드:

- id
- organization_id
- schedule_run_id
- group_id
- requires_proposal_ids
- affected_slot_id
- type
- source: server_generated
- affected_employee_ids
- affected_constraint_ids
- estimated_loss_score
- ranking_features_json
- anonymized_payload
- display_summary
- attempt_no
- status: suggested, approved, rejected

LLM 설명은 `display_summary`를 보강할 수 있지만, 완화안의 원본 판단 근거가 되어서는 안 됩니다.

`group_id`와 `requires_proposal_ids`는 여러 완화안을 함께 승인해야만 해가 생기는 경우를 표현합니다. 관리자는 단일 완화안과 묶음 완화안을 구분해서 볼 수 있어야 합니다.

### SolverDiagnosticEvent

후보 제거와 관계형 충돌을 구조화해 저장합니다.

주요 필드:

- id
- organization_id
- schedule_run_id
- event_type: unary_exclusion, relational_conflict, infeasibility_core
- shift_slot_id
- role_id
- employee_id
- related_employee_ids
- constraint_type
- constraint_id
- metadata_json
- attempt_no
- created_at

### OverrideApproval

관리자가 승인한 예외 기록입니다.

주요 필드:

- id
- organization_id
- schedule_run_id
- relaxation_proposal_id
- proposal_group_id
- selected_proposal_id
- considered_proposal_ids
- approved_by
- type
- target_employee_id
- target_constraint_id
- target_json
- notification_required
- notification_recorded_by
- reason
- created_at

`target_employee_id`와 `target_constraint_id`만으로 표현하기 어려운 미배정 허용, 역할 인원 축소, 최소 휴식 위반, 묶음 완화안 승인은 `relaxation_proposal_id`, `proposal_group_id`, `target_json`으로 표현합니다. `considered_proposal_ids`에는 승인 화면에 제시된 대안을 기록하고, `selected_proposal_id`에는 관리자가 선택한 대안을 기록합니다.

### FairnessLedger

기간을 넘는 공정성을 계산하기 위한 직원별 집계입니다. 구현은 별도 테이블 또는 `Assignment` 기반 materialized view로 시작할 수 있습니다.

주요 필드:

- organization_id
- employee_id
- period_key
- total_shift_count
- night_shift_count
- weekend_shift_count
- override_count
- unavailability_override_count
- pair_override_count
- updated_at

### ImportBatch

엑셀 업로드 이력을 관리합니다.

주요 필드:

- id
- organization_id
- type: employees, roles, unavailability, pair_constraints, shift_slots
- mode: upsert, replace
- status
- uploaded_by
- validation_summary_json
- created_at

### AuditLog

민감한 변경과 예외 승인을 기록합니다.

주요 필드:

- id
- organization_id
- actor_user_id
- action
- target_type
- target_id
- metadata_json
- created_at

## 8. 시간 모델

근무표 품질과 중복 배정 판정은 시간 모델에 크게 의존합니다.

기본 원칙:

- 조직 timezone을 필수로 둡니다.
- 모든 실제 슬롯은 timezone이 적용된 `starts_at`, `ends_at` timestamp로 저장합니다.
- 22:00-06:00처럼 자정을 넘는 근무는 종료일을 다음 날짜로 계산합니다.
- 반복 규칙은 초기에는 일/주/월 프리셋으로 제한하고, 내부 표현은 RRULE 확장을 고려합니다.
- 휴일, 예외일, 반복 제외일을 `recurrence_exceptions` 또는 별도 calendar table로 처리합니다.
- DST 전환일은 timezone 라이브러리의 변환 결과를 따르며, 애매하거나 존재하지 않는 로컬 시간은 생성 전 검증 오류로 표시합니다.
- 불가 일정은 날짜 전체와 부분일을 모두 지원하며, 슬롯 겹침 기준으로 배정 가능 여부를 판단합니다.

## 9. 제약 정책

제약은 `절대 불가`, `승인 시 완화 가능`, `점수 기반 최적화` 세 단계로 나눕니다. 이 분류는 solver 모델링과 관리자 UX를 동시에 결정합니다.

### 9.1 절대 불가 제약

어떤 경우에도 시스템이 완화 후보로 제시하지 않는 제약입니다.

- 비활성 직원 배정 금지
- 역할 자격이 없는 직원 배정 금지
- 같은 시간대 동일 직원 중복 배정 금지
- 동일 슬롯에서 동일 직원 중복 배정 금지
- 조직이 다른 데이터 간 교차 배정 금지
- 잠긴 확정 근무표의 승인 없는 변경 금지

### 9.2 승인 시 완화 가능 제약

1차 생성에서는 반드시 지키지만, 미배정 손실을 줄일 수 있을 때 관리자에게 완화 후보로 제시할 수 있는 제약입니다.

- 휴가 중 배정
- 출장/교육 중 배정
- 개인 일정 중 배정
- `blocked` 조합 동시 배정
- 최소 휴식 시간 위반
- 연속 근무 제한 위반

이 제약은 solver가 자동으로 깨지 않습니다. 관리자 승인 전에는 근무표에 반영하지 않습니다.

### 9.3 점수 기반 최적화 제약

해의 품질을 높이기 위한 제약입니다.

- 직원별 근무 횟수 균형
- 주말/야간 근무 균형
- 필요 역할/필요 인원 미충족 최소화
- 직원 선호일 반영
- 최근 근무자 반복 배정 최소화
- `avoid` 조합 회피
- `prefer` 조합 선호

## 10. 기본 손실 점수와 랭킹

초기 기본 정책은 다음과 같이 둡니다. 실제 점수는 조직별 고급 설정에서 조정할 수 있습니다.

| 항목 | 기본 손실 점수 | 설명 |
| --- | ---: | --- |
| 기본 사수 역할 미배정 | 1000 | 운영상 가장 큰 문제로 봅니다. 실제 값은 역할별 설정으로 대체할 수 있습니다. |
| 기본 부사수 역할 미배정 | 800 | 운영상 큰 문제로 봅니다. 실제 값은 역할별 설정으로 대체할 수 있습니다. |
| 출장/교육 중 배정 | 700 | 실제 업무상 대체가 어렵다고 봅니다. |
| 휴가 중 배정 | 600 | 개인 권리 침해 가능성이 커서 높은 손실로 봅니다. |
| 상극 조합 동시 배정 | 600 | 조직 리스크가 크므로 높은 손실로 봅니다. |
| 개인 일정 중 배정 | 400 | 휴가보다 낮지만 중요한 제약으로 봅니다. |
| 최소 휴식 시간 위반 | 300 | 피로도와 안전 리스크입니다. |
| 연속 근무 제한 위반 | 250 | 피로도와 공정성 리스크입니다. |
| 근무량 불균형 | 100 | 장기 공정성 문제입니다. |
| 선호일 위반 | 50 | 가능하면 반영하되, 운영 제약보다 낮게 둡니다. |

승인 시 완화 가능 제약의 손실 점수는 1차 엄격 생성의 solver objective에 넣지 않습니다. 해당 점수는 실패 진단, 완화안 후보 비교, 관리자 승인 화면의 랭킹에 사용합니다. 미배정 손실과 점수 기반 최적화 제약은 1차 생성의 objective에 들어갑니다.

초기 objective 정의:

- 미배정 손실: `ShiftRequirement.unfilled_weight_override`, `SchedulePolicyRoleWeight.unfilled_weight`, `SchedulePolicy.default_unfilled_requirement_weight` 순서로 역할별 가중치를 결정하고, 미충족 인원 수에 곱합니다.
- 근무량 불균형: 직원별 배정 횟수의 `max_count - min_count` 또는 목표 근무 수 대비 L1 편차로 계산합니다.
- 선호일 위반: 선호하지 않는 슬롯에 배정된 횟수에 가중치를 곱합니다.
- `avoid` 조합 회피 실패: 같은 슬롯에 배정된 avoid 조합 수에 가중치를 곱합니다.
- `prefer` 조합 선호 충족: 같은 슬롯에 배정된 prefer 조합 수를 보상 점수로 반영합니다.

랭킹 레이어에서 추가로 반영하는 요소:

- 해당 직원의 최근 양보 누적 횟수
- 해당 직원의 최근 근무 횟수
- 해당 역할을 대체할 수 있는 후보 수
- 하나의 완화안이 해결하는 슬롯 수
- 완화안이 다른 충돌을 새로 만드는지 여부

이 추가 요소는 서버의 post-solve 랭킹 휴리스틱으로 계산합니다. 후보 수 폭발을 막기 위해 기본적으로 상위 `proposal_top_n`개만 관리자에게 표시합니다.

## 11. 근무표 생성 로직

### 11.1 입력 검증과 진단 이벤트

solver 실행 전에 서버는 슬롯별, 역할별 후보자를 계산합니다. 이 단계에서 단일 후보 기준으로 판단할 수 있는 제외 사유는 `unary_exclusion` 이벤트로 남깁니다.

unary exclusion 예:

```json
{
  "slot_id": "SLOT-001",
  "role_id": "assistant",
  "employee_id": "EMP-014",
  "event_type": "unary_exclusion",
  "excluded_by": "VACATION",
  "constraint_id": "UNAVAILABLE-003"
}
```

조합 제한처럼 다른 직원 배정과 함께 발생하는 제약은 사전 후보 제거 로그로 표현하지 않고 `relational_conflict` 이벤트로 남깁니다.

relational conflict 예:

```json
{
  "slot_id": "SLOT-001",
  "event_type": "relational_conflict",
  "employee_id": "EMP-014",
  "related_employee_ids": ["EMP-022"],
  "constraint_type": "PAIR_BLOCKED",
  "constraint_id": "PAIR-003"
}
```

이 진단 이벤트는 실패 진단과 LLM 설명의 원천 데이터입니다. CP-SAT의 `INFEASIBLE` 결과만으로 설명을 만들지 않습니다.

### 11.2 1차 엄격 생성

1. 입력 데이터를 검증합니다.
2. 근무 슬롯과 역할 요구사항을 생성합니다.
3. 직원별 가능 역할, 불가 일정, 조합 제한을 계산합니다.
4. 절대 불가 제약과 승인 시 완화 가능 제약을 모두 활성화합니다.
5. 점수 기반 최적화 제약을 objective로 구성합니다.
6. OR-Tools CP-SAT solver로 가능한 근무표를 탐색합니다.
7. 가능한 해가 있으면 공정성, 선호도, avoid/prefer 조합 같은 점수 기반 최적화 제약으로 더 좋은 해를 선택합니다.

### 11.3 실패 진단 모델

1차 생성이 실패하거나 높은 손실의 ScheduleIssue가 남으면 승인 시 완화 가능 제약에 assumption literal 또는 enforcement literal을 붙인 진단 모델을 실행합니다. 완화 단위는 제약 종류 전체가 아니라 인스턴스 단위입니다. 예를 들어 휴가 완화는 `(employee, slot)`, 조합 완화는 `(employee_a, employee_b, slot)`, 미배정 이슈는 `(slot, role, missing_count)` 단위로 둡니다.

진단 목표:

- 어떤 슬롯이 채워지지 않았는지
- 어떤 역할의 후보가 부족한지
- 어떤 승인 가능 제약이 병목인지
- 어떤 제약을 완화하면 미배정 손실을 줄일 수 있는지

OR-Tools의 assumption 기반 infeasibility 분석은 충분한 충돌 집합을 찾는 용도로 사용합니다. 이 결과가 항상 전역 최소 완화안이라고 가정하지 않고, 서버가 후보를 재시뮬레이션하고 손실 점수로 다시 랭킹합니다.

### 11.4 완화안 생성

시스템은 다음 후보를 생성합니다.

- 휴가 중 1회 근무 예외 승인
- 출장/교육 중 1회 근무 예외 승인
- 개인 일정 중 1회 근무 예외 승인
- 상극 조합 1회 완화
- 최소 휴식 시간 1회 완화
- 연속 근무 제한 1회 완화
- 해당 슬롯 미배정 유지
- 역할 요구 인원 임시 축소
- 수동 조정 필요 표시

각 후보는 손실 점수와 영향 범위를 갖습니다. 가능한 경우 상위 N개를 표시하고, 2개 미만이면 왜 추가 후보가 없는지 설명합니다.

여러 완화안을 동시에 승인해야 해가 생기는 경우에는 단일 후보로 오해하지 않도록 같은 `group_id`를 부여하고 묶음 승인 필요 상태로 표시합니다.

### 11.5 관리자 승인 후 재계산

관리자가 완화안을 승인하면 해당 예외를 `OverrideApproval`로 저장하고 근무표를 다시 계산합니다. 승인하지 않으면 미배정 또는 수동 조정 상태로 남깁니다.

재계산 규칙:

- 승인된 OverrideApproval은 다음 solver 실행에서 고정 제약으로 반영합니다.
- 사용자가 수동 수정한 Assignment는 기본적으로 `locked_by_user=true`로 저장하고, 재계산 시 고정 배정으로 유지합니다.
- 관리자가 명시적으로 잠금을 해제한 수동 배정만 solver가 다시 바꿀 수 있습니다.
- 관리자 승인 또는 수동 변경으로 재계산할 때는 같은 ScheduleRun의 `recalculation_count`를 증가시킵니다.
- worker의 일시적 실패 재시도는 `current_attempt_no`만 증가시키며 `recalculation_count`를 소진하지 않습니다.
- 1차 릴리즈의 최대 재계산 라운드는 `recalculation_count` 기준 3회입니다. 초과 시 `manual_review_required` ScheduleIssue를 생성합니다.
- 같은 ScheduleIssue와 같은 제약 조합이 반복되면 루프로 판단하고 추가 자동 재계산을 중단합니다.
- 묶음 완화안이 필요한데 1차 UI에서 묶음 승인을 지원하지 않는 경우, 해당 묶음은 읽기 전용으로 표시하고 `수동 조정 필요` 또는 `미배정 유지` 폴백을 함께 제공합니다.
- 재계산 후 새 ScheduleIssue가 생기면 이전 이슈와 새 이슈를 attempt 단위로 구분해 보여줍니다.

### 11.6 확정과 잠금

관리자가 최종 확정한 근무표는 `SchedulePublication`으로 생성하고 입력 스냅샷, assignment snapshot hash, issue snapshot hash와 함께 보존합니다. 확정 이후 직원, 휴가, 조합 제한이 바뀌어도 기존 ScheduleRun과 SchedulePublication의 결과는 자동 변경하지 않습니다. 변경이 필요하면 새 ScheduleRun을 생성한 뒤 새 publication으로 발행합니다.

## 12. AI/LLM 역할

LLM은 근무표를 직접 생성하지 않습니다. 근무표 생성과 완화안 후보 생성은 서버와 제약 최적화 엔진이 담당합니다.

LLM 담당 기능:

- 충돌 원인 자연어 요약
- 완화안 설명
- 관리자에게 보여줄 추천 이유 작성
- 생성된 근무표의 품질 요약
- 엑셀 업로드 오류 메시지 정리

LLM이 하지 않는 일:

- 최종 배정 결정
- 완화안 원본 생성
- 제약 자동 완화
- 승인 없이 휴가자 배정
- 실명 기반 민감 정보 처리

## 13. LLM 익명화와 개인정보 보호

LLM에는 조직명, 직원 실명, 개인 일정 상세 사유를 보내지 않습니다. `E003`처럼 조직 내에서 반복되는 안정적 식별자도 재식별 위험이 있으므로 사용하지 않습니다.

원칙:

- 요청 단위 임시 pseudonym을 사용합니다.
- pseudonym 매핑 테이블은 요청 처리 중 메모리에만 두고 영속 저장하지 않습니다.
- LLM에는 최소한의 슬롯 정보, 제약 유형, 후보 수, 손실 수준만 전달합니다.
- `estimated_loss_score` 같은 숫자 점수는 LLM에 전달하지 않고 서버 템플릿이 표시합니다. LLM은 정성 설명만 생성합니다.
- 직원 메모, 휴가 사유, 자유 텍스트 note, 업로드 원문 문구는 LLM에 전달하지 않습니다.
- 소규모 조직에서는 날짜, 역할, 제외 사유 조합만으로도 재식별 위험이 있으므로 전송 필드를 더 줄입니다.
- provider 로그 보관 정책과 데이터 학습 사용 여부를 검토하고, 운영 환경에서는 저장 제한 또는 enterprise 옵션을 우선 검토합니다.
- 모든 LLM 요청은 AuditLog에 provider, 목적, 전송 필드 범위, 요청자만 기록하고 원문 민감 데이터는 저장하지 않습니다.

LLM 입력 예:

```json
{
  "slot_label": "target slot",
  "missing_role": "assistant",
  "excluded_candidates": [
    {"employee": "P1", "reason": "VACATION"},
    {"employee": "P2", "reason": "BUSINESS_TRIP"}
  ],
  "relational_conflicts": [
    {"employees": ["P3", "P4"], "reason": "PAIR_BLOCKED"}
  ],
  "available_relaxations": [
    "APPROVE_TIME_OFF_OVERRIDE",
    "RELAX_PAIR_BLOCK_ONCE",
    "LEAVE_UNASSIGNED"
  ]
}
```

서버는 LLM 응답을 받은 뒤 내부 매핑을 통해 관리자 화면에 실제 이름과 설명을 표시합니다.

### 13.1 LLM Output Contract

LLM은 구조화된 JSON만 반환합니다. 자유 문장을 그대로 신뢰하지 않습니다.

```json
{
  "summary": "부사수 후보가 부족합니다.",
  "reason_bullets": [
    "일부 후보는 휴가 또는 출장으로 제외되었습니다.",
    "일부 후보는 조합 제한으로 함께 배정할 수 없습니다."
  ],
  "recommended_action_label": "예외 승인 후보를 검토하세요.",
  "caution_level": "high"
}
```

Schema 제한:

- `summary`: required, string, 최대 120자
- `reason_bullets`: required, string array, 최대 3개, 항목당 최대 120자
- `recommended_action_label`: required, string, 최대 80자
- `caution_level`: required enum, `none | low | medium | high`

허용:

- 서버가 제공한 reason code를 자연어로 바꾸기
- 서버가 제공한 proposal type을 쉬운 문장으로 설명하기
- 관리자 확인이 필요하다는 표현

금지:

- 서버가 제공하지 않은 원인 만들기
- 특정 직원이 반드시 양보해야 한다고 단정하기
- 법적 준수를 보장한다고 표현하기
- 최적해가 아닌 결과를 최적이라고 표현하기
- 내부 점수 숫자를 임의로 말하기

Fallback:

- LLM 호출이 실패하면 서버 템플릿 문구를 사용합니다.
- LLM 응답이 schema validation에 실패하면 폐기하고 fallback을 사용합니다.
- LLM 설명은 ScheduleRun 완료를 막지 않습니다. 결과와 구조화 완화안은 먼저 표시하고, 설명은 비동기로 보강합니다.

Eval:

- anonymized payload와 기대 설명을 묶은 golden set을 둡니다.
- reason code 왜곡, proposal type 왜곡, 개인정보 누출, 금지 표현을 자동 검사합니다.
- CI에서는 reason code 왜곡 0건, proposal type 왜곡 0건, 개인정보 누출 0건을 통과 기준으로 둡니다.
- 문장 톤 차이는 허용하지만, 원인과 조치 유형의 의미가 바뀌면 실패로 봅니다.
- 업로드 텍스트나 note에서 prompt injection 문구가 들어와도 LLM payload에 포함되지 않는지 테스트합니다.
- 소규모 조직 샘플에서 재식별 가능성이 높은 payload를 줄이는지 검토합니다.

## 14. 엑셀 업로드/다운로드

### 14.1 업로드 대상

- 직원 목록
- 직원별 역할 가능 여부
- 휴가/출장/개인 일정
- 조합 제한
- 근무 슬롯 또는 근무 요구사항

### 14.2 업로드 처리

1. 템플릿 파일을 제공합니다.
2. 사용자가 엑셀을 업로드합니다.
3. 서버가 컬럼명과 데이터 형식을 검증합니다.
4. 오류가 있으면 행 번호, 컬럼명, 오류 사유를 반환합니다.
5. 문제가 없으면 임시 미리보기를 보여줍니다.
6. 관리자가 확인하면 실제 데이터에 반영합니다.

업로드 기본 동작은 자연키 기준 upsert입니다.

- 직원: `employee_code`
- 역할: `role_name`
- 근무 유형: `shift_type_name`
- 조합 제한: `employee_code_a + employee_code_b + constraint_type`

전체 replace는 기존 데이터 삭제 영향이 크므로 별도 확인 화면을 거칩니다.

### 14.3 다운로드 대상

- 직원 목록
- 휴가표
- 제약 설정
- 생성된 근무표
- 예외 승인 이력

MVP에서는 다운로드를 먼저 구현하고, 업로드는 v1 범위로 둡니다.

### 14.4 Excel 기반 온보딩

HR 사용자는 기존 Excel 업무 흐름에서 전환하는 경우가 많으므로, 1차 릴리즈에서도 다음을 제공합니다.

- 직원 목록 bulk paste 입력
- 휴가/출장/개인 일정 bulk paste 입력
- 조합 제한 bulk paste 입력
- 붙여넣기 후 행 단위 검증 결과 표시
- 생성된 근무표 Excel 다운로드
- 기존 Excel 양식으로 재가공하기 쉬운 컬럼명 유지

정식 `.xlsx` 업로드와 검증 미리보기는 v1 범위로 둡니다. 단, 1차 릴리즈의 bulk paste는 50명 이상 초기 입력 부담을 줄이는 최소 대안입니다.

1차 bulk paste 컬럼:

직원:

```text
employee_code, name, roles, active
```

불가 일정:

```text
employee_code, type, starts_at, ends_at, override_allowed
```

조합 제한:

```text
employee_code_a, employee_code_b, type, override_allowed
```

날짜/시간은 ISO 형식 또는 조직 timezone 기준 `YYYY-MM-DD HH:mm` 형식을 허용합니다. 이 컬럼들은 v1 Excel 업로드 템플릿과 동일하게 유지합니다.

### 14.5 HR 고지와 통지

- 휴가 중 배정, 최소 휴식 위반, 상극 조합 완화는 승인 전 확인 문구를 표시합니다.
- 휴가 중 배정 예외 승인 시 `당사자 통지 필요` 체크 항목을 표시합니다.
- 휴가 중 배정 예외 승인 화면에는 `당사자 동의와 통지는 관리자 책임입니다`라는 확인 문구를 표시합니다.
- 1차 릴리즈에서는 자동 통지를 제공하지 않지만, 관리자가 수동 통지 여부를 기록할 수 있게 합니다.
- 제품은 법적 준수 보증 도구가 아니라 조직 설정값 기준의 스케줄링 보조 도구임을 설정 화면과 결과 화면에 표시합니다.
- 예외 승인에는 승인자, 승인 시각, 사유, 선택한 대안, 통지 여부를 남깁니다.

## 15. 화면 구성과 구현 순서

### MVP 화면

1. 로그인/회원가입
2. 조직 선택/생성
3. 직원/역할 관리
4. 근무 유형/템플릿 관리
5. 휴가/출장/개인 일정 관리
6. 조합 제한 관리
7. 근무표 생성/결과/완화안 검토
8. 엑셀 다운로드

### v1 화면

1. 엑셀 업로드/검증 미리보기
2. 고급 정책 설정
3. 예외 승인 이력
4. 생성 이력 비교
5. 일반 사용자 근무표 조회

### v2 화면

1. 일반 사용자 휴가/일정 요청
2. 조직 초대와 EmployeeUserLink 관리
3. 감사 로그 조회
4. 공정성 대시보드
5. 알림 설정

### 15.1 결과/예외 화면 UI Acceptance Criteria

근무표 생성 결과 화면은 운영 도구형 UI로 설계합니다. 마케팅형 AI 화면이나 큰 설명 위주의 화면은 피하고, 그리드, 이슈, 추천, 재계산 액션을 한 흐름에서 보여줍니다.

상태별 UI:

- `queued`: 생성 요청 접수, 대기 순서 또는 대기 상태, 취소 버튼 표시
- `running`: 진행 중 표시, 시작 시각, timeout 기준 남은 시간, 취소 버튼 표시
- `succeeded + optimal`: 결과 그리드, 품질 요약, 확정 버튼 표시
- `succeeded + feasible_not_proven_optimal`: 결과 그리드와 `최적 보장 없음` 배지 표시
- `infeasible`: 이슈 목록과 완화안 표시, 확정 버튼 비활성화
- `failed`: 오류 요약과 재시도 버튼 표시
- `canceled`: 취소됨 표시, 새 생성 버튼 표시
- `published`: 읽기 전용 결과와 다운로드 버튼 표시

결과 그리드:

- 행은 날짜/슬롯, 열은 역할을 기본 구조로 둡니다.
- 각 셀은 배정 직원, 역할, source(`solver/manual/override`), 경고 상태를 표시합니다.
- 미배정 셀과 `미배정으로 확정` 상태는 시각적으로 구분합니다.
- 1차 릴리즈에서는 클릭 후 모달 또는 사이드 패널로 수동 수정합니다. 드래그 앤 드롭은 제외합니다.
- 수동 수정 후에는 서버 검증을 다시 실행하고, 위반이 있으면 저장을 막거나 ScheduleIssue로 표시합니다.
- 100명/31일 화면을 고려해 테이블 가상 스크롤 또는 pagination을 전제로 합니다.

이슈/완화안 패널:

- ScheduleIssue는 심각도, 슬롯, 역할, 사유, 영향 범위를 표시합니다.
- 내부 점수 숫자는 기본 UI에 직접 노출하지 않고 `높음/중간/낮음` 같은 등급으로 번역합니다.
- RelaxationProposal 카드는 추천 이유, 승인 영향, 대체안, 재계산 예상 결과를 표시합니다.
- 묶음 완화안은 같은 시각적 그룹으로 묶고, 1차 릴리즈에서는 읽기 전용 또는 후속 기능으로 표시합니다.
- 휴가 중 배정, 휴식 시간 위반, 조합 제한 완화는 승인 전 확인 문구를 요구합니다.

Severity 라벨:

| 내부 값 | 한국어 라벨 | 사용 예 |
| --- | --- | --- |
| none | 없음 | 이슈 없음 |
| low | 낮음 | 선호일 위반, 작은 공정성 편차 |
| medium | 주의 | 반복 근무 쏠림, avoid 조합 |
| high | 높음 | 미배정, 휴가 예외 후보, 조합 제한 후보 |
| critical | 매우 높음 | 사수 미배정, 확정 불가 상태 |

온보딩/입력:

- 조직 설정 마법사는 진행률, 임시저장, 건너뛰기를 지원합니다.
- 엑셀 업로드가 1차 범위에 없더라도 직원/휴가/조합 제한은 paste 가능한 bulk entry grid를 제공합니다.
- 법적 준수 보증이 아니라 조직 설정값 기준 보조 기능이라는 안내를 설정과 결과 화면에 표시합니다.

## 16. 아키텍처

### 16.1 권장 기술 스택

- Frontend: React 또는 Next.js
- Backend API: FastAPI
- Solver: Python OR-Tools CP-SAT
- Database: PostgreSQL
- Tenant isolation: PostgreSQL RLS + application-level organization scope
- ORM/Migration: SQLAlchemy + Alembic
- Background job: Redis queue + solver worker
- LLM Provider: provider 교체 가능한 인터페이스
- Deployment: Railway

기술 선택 메모:

- OR-Tools를 선택합니다. Python/FastAPI와 같은 런타임에서 solver를 직접 제어할 수 있고, 과제 범위에서 제약 모델을 투명하게 설명하기 쉽기 때문입니다.
- Timefold/OptaPlanner는 employee scheduling 도메인 기능과 score 분석이 강하지만, Java 생태계와 플랫폼 복잡도가 커져 1차 릴리즈에는 부담이 큽니다.
- LLM은 provider 교체 가능하게 두되, 1차 릴리즈에서는 구조화 출력이 안정적이고 비용이 낮은 모델을 우선합니다.

### 16.2 서버 구성

Backend는 다음 모듈로 나눕니다.

- Auth: 로그인, 조직 멤버십, 권한
- Tenant Context: RLS context 설정과 organization scope 검증
- Master Data: 직원, 역할, 근무 유형
- Calendar Data: 휴가, 출장, 개인 일정
- Constraint Data: 조합 제한, 정책 가중치
- Scheduling API: 생성 요청 접수, 실행 상태 조회, 결과 저장
- Solver Worker: 슬롯 생성, 최적화 실행, 실패 진단, 완화안 랭킹
- Explanation: 익명화, LLM 요청, 설명 결과 매핑
- Import/Export: 엑셀 업로드/다운로드
- Audit: 예외 승인, 민감한 변경, LLM 요청 기록

Tenant Context 정책:

- tenant 데이터가 있는 모든 테이블에는 `organization_id`를 둡니다.
- `EmployeeRole`, `ShiftRequirement`, `Assignment`, `RelaxationProposal` 같은 자식/조인 테이블도 RLS 단순화를 위해 `organization_id`를 비정규화해 저장합니다.
- 각 DB transaction 시작 시 `SET LOCAL app.current_organization_id = ...`를 설정합니다.
- RLS 정책은 기본적으로 `organization_id = current_setting('app.current_organization_id')::uuid` 형태를 사용합니다.
- 애플리케이션 레이어에서도 모든 repository/query가 organization scope를 인자로 받도록 강제합니다.

### 16.3 생성 요청 처리 흐름

```text
관리자 요청
  -> API가 ScheduleRun 생성(status=queued)
  -> 입력 snapshot과 organization_data_version 저장
  -> Redis queue에 solver job 등록
  -> Solver Worker가 job 수신(status=running)
  -> 입력 데이터 검증과 후보 제거 로그 생성
  -> 근무 슬롯 생성
  -> 제약 모델 구성
  -> OR-Tools solver 실행
  -> 성공: 근무표 저장 및 품질 요약
  -> 실패: 진단 모델 실행
  -> 완화 후보 생성과 top-N 랭킹
  -> ScheduleRun 상태 갱신
  -> 필요 시 익명화된 설명 job 등록
  -> LLM 설명은 비동기로 생성하고 실패 시 서버 fallback 유지
  -> 관리자 화면에서 polling 또는 refresh로 결과 표시
```

### 16.4 동시성과 스냅샷

- 생성 요청 시점의 입력 데이터를 snapshot으로 저장합니다.
- 생성 중 직원, 휴가, 조합 제한이 바뀌어도 현재 ScheduleRun에는 영향을 주지 않습니다.
- 같은 조직에서 여러 ScheduleRun을 동시에 만들 수는 있지만, active SchedulePublication은 한 기간에 하나만 허용하는 정책을 기본값으로 둡니다.
- publication 충돌은 optimistic locking 또는 unique constraint로 막습니다.
- 취소 요청은 ScheduleRun 상태를 `canceled`로 바꾸고 worker가 주기적으로 확인합니다.

### 16.5 API Contract Sketch

정식 OpenAPI는 구현 계획 단계에서 작성합니다. 기획 단계에서는 프론트/백엔드 병렬 개발을 위해 핵심 응답 형태를 먼저 고정합니다.

조회 규칙:

- 생성 상태 polling 기본 주기는 2초입니다.
- `running` 상태가 30초를 넘으면 5초 주기로 낮춥니다.
- 목록 API는 cursor 기반 pagination을 사용합니다.
- 상태 조회 응답은 `updated_at` 또는 ETag를 제공해 불필요한 재렌더링을 줄입니다.

ScheduleRun response:

```json
{
  "id": "run_123",
  "organization_id": "org_123",
  "period_start": "2026-07-01",
  "period_end": "2026-07-07",
  "status": "running",
  "solver_status": null,
  "solution_quality": "unknown",
  "progress": {
    "phase": "building_model",
    "message": "근무표 모델을 구성하는 중입니다.",
    "started_at": "2026-07-01T00:00:00Z",
    "timeout_seconds": 30
  },
  "score_summary": {
    "hard": 0,
    "approvable": 0,
    "soft": 0,
    "severity_label": "none"
  },
  "issues": [],
  "proposals": []
}
```

ScheduleIssue response:

```json
{
  "id": "issue_123",
  "shift_slot_id": "slot_123",
  "role_id": "role_assistant",
  "type": "unfilled_requirement",
  "missing_count": 1,
  "severity": "high",
  "reason_code": "NO_AVAILABLE_CANDIDATE",
  "display_message": "부사수 후보가 부족합니다."
}
```

RelaxationProposal response:

```json
{
  "id": "proposal_123",
  "group_id": null,
  "requires_proposal_ids": [],
  "type": "approve_time_off_override",
  "severity": "high",
  "affected_slot_id": "slot_123",
  "display_summary": "휴가 중인 후보 1명을 1회 예외 승인하면 미배정을 해소할 수 있습니다.",
  "impact_preview": {
    "resolved_issue_ids": ["issue_123"],
    "new_warning_count": 1
  },
  "status": "suggested"
}
```

Manual edit validation response:

```json
{
  "valid": false,
  "blocking_errors": [
    {
      "code": "ROLE_NOT_ALLOWED",
      "message": "해당 직원은 부사수 역할을 맡을 수 없습니다.",
      "field": "employee_id"
    }
  ],
  "warnings": []
}
```

`GET /schedule-runs/{id}/result` response:

```json
{
  "schedule_run_id": "run_123",
  "read_only": false,
  "publication": null,
  "slots": [
    {
      "id": "slot_2026_07_01_day",
      "local_date": "2026-07-01",
      "label": "주간 근무",
      "starts_at": "2026-07-01T09:00:00+09:00",
      "ends_at": "2026-07-01T18:00:00+09:00"
    }
  ],
  "requirements": [
    {
      "id": "req_1",
      "slot_id": "slot_2026_07_01_day",
      "role_id": "role_senior",
      "role_name": "사수",
      "required_count": 1
    }
  ],
  "assignments": [
    {
      "id": "assign_1",
      "slot_id": "slot_2026_07_01_day",
      "role_id": "role_senior",
      "employee_id": "emp_1",
      "employee_name": "김OO",
      "source": "solver",
      "locked_by_user": false,
      "warning_state": "none"
    }
  ],
  "issues": [
    {
      "id": "issue_1",
      "slot_id": "slot_2026_07_01_day",
      "role_id": "role_assistant",
      "type": "unfilled_requirement",
      "severity": "high",
      "display_message": "부사수 1명이 미배정입니다."
    }
  ],
  "proposals": [
    {
      "id": "proposal_1",
      "type": "approve_time_off_override",
      "severity": "high",
      "status": "suggested",
      "display_summary": "휴가 중인 후보 1명을 예외 승인하면 미배정을 해소할 수 있습니다."
    }
  ]
}
```

### 16.6 DB Invariants

주요 invariant:

- `organizations.name`은 전역 unique가 아니어도 됩니다.
- `employees(organization_id, employee_code)`는 unique입니다.
- `roles(organization_id, name)`은 unique입니다.
- `shift_types(organization_id, name)`은 unique입니다.
- `pair_constraints`는 `(organization_id, normalized_employee_a_id, normalized_employee_b_id, type)` unique로 대칭 중복을 막습니다.
- `normalized_employee_a_id`와 `normalized_employee_b_id`는 write 시점에 작은 employee id가 a, 큰 employee id가 b가 되도록 정규화합니다.
- `pair_constraints`는 `normalized_employee_a_id < normalized_employee_b_id` check constraint를 둡니다.
- `assignments(schedule_run_id, shift_slot_id, role_id, employee_id)`는 unique입니다.
- `assignments(schedule_run_id, shift_slot_id, employee_id)`도 unique입니다. 1차 릴리즈에서는 한 직원이 같은 슬롯에서 여러 역할을 동시에 맡을 수 없습니다.
- 같은 슬롯/역할의 필요 인원 수를 넘는 assignment는 application validation과 solver output validation으로 막습니다.
- `schedule_publications`는 같은 조직/기간의 active publication이 하나만 존재하도록 partial unique index를 둡니다.
- `unavailability(employee_id, starts_at, ends_at)` 조회를 위해 overlap 검색 index를 둡니다.
- 자식 테이블의 `organization_id`는 복합 FK 또는 트리거로 부모와 일치하도록 강제합니다.

RLS와 migration:

- RLS 정책과 `FORCE ROW LEVEL SECURITY`는 Alembic raw SQL migration으로 관리합니다.
- connection pool 사용 시 tenant context는 트랜잭션 안에서 `SET LOCAL app.current_organization_id = ...`로 설정합니다.
- PgBouncer transaction pooling을 사용할 경우 세션 변수 지속성에 의존하지 않습니다.

### 16.7 Worker Retry And Idempotency

- 생성 요청은 `idempotency_key`를 받을 수 있습니다.
- 같은 조직, 같은 입력 snapshot hash, 같은 idempotency key로 중복 요청이 오면 기존 ScheduleRun을 반환합니다.
- 같은 조직과 같은 idempotency key지만 snapshot hash가 다르면 `409 Conflict`를 반환합니다.
- 새 입력으로 새 ScheduleRun을 만들려면 클라이언트는 새 idempotency key를 발급해야 합니다.
- worker retry는 같은 ScheduleRun에 대해 수행합니다.
- worker retry는 `current_attempt_no`를 증가시키며 수행합니다.
- 관리자 승인 또는 수동 변경 기반 재계산만 `recalculation_count`를 증가시킵니다.
- 재시도 전 기존 partial Assignment, ScheduleIssue, SolverDiagnosticEvent는 이전 `attempt_no` 단위로 정리하거나 비활성화합니다.
- worker는 `queued -> running -> succeeded/infeasible/failed/canceled` 상태 전이를 원자적으로 갱신합니다.
- 취소된 ScheduleRun은 worker가 다음 checkpoint에서 중단합니다.
- `organization_data_version`은 직원, 역할, 근무 유형, 불가 일정, 조합 제한, 정책 변경 시 증가합니다.

## 17. Railway 배포 방향

Railway 배포는 API, solver worker, PostgreSQL, Redis를 분리하는 구성을 권장합니다.

권장 서비스:

- Web/API service: FastAPI
- Worker service: solver worker
- PostgreSQL service: 영속 데이터
- Redis service: job queue

권장 흐름:

1. GitHub 저장소를 준비합니다.
2. Railway 프로젝트를 생성합니다.
3. PostgreSQL 서비스를 추가합니다.
4. Redis 서비스를 추가합니다.
5. API 서비스를 GitHub repo 또는 Dockerfile로 배포합니다.
6. Worker 서비스를 같은 repo의 별도 start command로 배포합니다.
7. Railway private networking으로 API와 worker가 내부 통신하도록 구성합니다.
8. 환경 변수를 설정합니다.
   - `DATABASE_URL`
   - `REDIS_URL`
   - `JWT_SECRET`
   - `LLM_PROVIDER`
   - `LLM_API_KEY`
   - `APP_ENV`
9. 배포 전 migration을 실행합니다.
10. 프론트엔드는 같은 Railway 프로젝트의 별도 서비스 또는 정적 배포로 구성합니다.

FastAPI의 내장 BackgroundTasks는 짧은 후처리에는 사용할 수 있지만, CPU-bound solver 실행은 별도 worker로 분리합니다.

## 18. 성공 기준

### 18.1 1차 완성 성공 기준

기능 기준:

- 조직을 만들고 직원 2~100명을 등록할 수 있습니다.
- 기본 템플릿으로 사수 1명, 부사수 1명 근무표를 생성할 수 있습니다.
- 커스텀 역할과 역할별 필요 인원 수를 설정할 수 있습니다.
- 휴가/출장/개인 일정이 반영됩니다.
- 상극 조합이 반영됩니다.
- 미배정이 필요한 경우 ScheduleIssue로 저장하고 높은 손실로 표시합니다.
- 미배정 손실을 줄일 수 있는 승인 후보가 있으면 가능한 완화안을 최대 N개 제시합니다.
- 완화안이 2개 미만이면 추가 후보가 없는 이유를 표시합니다.
- 완화안을 승인하면 승인 기록이 남고 재계산할 수 있습니다.
- 미배정 또는 인원 축소가 필요한 경우 ScheduleIssue로 저장하고 관리자 화면에 표시합니다.
- 관리자가 검토 완료한 근무표는 SchedulePublication으로 발행되고 읽기 전용으로 잠깁니다.
- 엑셀 다운로드가 가능합니다.
- LLM은 서버가 만든 완화안과 충돌 원인을 관리자용 문장으로 설명합니다.
- LLM에는 요청 단위로 익명화된 최소 데이터만 전달됩니다.
- Railway에 API와 worker를 배포할 수 있습니다.

품질 기준:

- 생성 결과가 제약 위반 여부를 명확히 표시합니다.
- 관리자는 왜 특정 추천안이 제시됐는지 이해할 수 있습니다.
- solver가 제한 시간 안에 `FEASIBLE`만 반환한 경우 `최적 보장 없음` 상태를 표시합니다.
- 재현성 우선 모드에서는 동일 입력, 동일 snapshot, 동일 solver/model version, 동일 seed, 동일 worker 수로 같은 결과를 얻을 수 있습니다.
- 실패 시에도 단순 오류가 아니라 조치 가능한 진단을 제공합니다.
- solver 모델은 golden case 회귀 테스트를 갖습니다.

### 18.2 후속 v1 성공 기준

- 엑셀 업로드와 검증 미리보기를 제공합니다.
- 업로드 검증은 행 번호, 컬럼명, 오류 사유를 반환합니다.
- 고급 정책 UI에서 조직별 가중치를 수정할 수 있습니다.
- 생성 이력 비교를 제공합니다.
- 일반 사용자가 본인 근무표를 조회할 수 있습니다.

### 18.3 후속 v2 성공 기준

- 일반 사용자가 휴가/일정 요청을 등록할 수 있습니다.
- 조직 초대와 EmployeeUserLink 관리 흐름을 제공합니다.
- 감사 로그 조회 화면을 제공합니다.
- 장기 공정성 대시보드를 제공합니다.

### 18.4 도입 성공 지표

1차 릴리즈부터 다음 지표를 남길 수 있게 설계합니다.

- 근무표 1건 생성에 걸린 시간
- 첫 생성 성공률
- 생성 후 수동 수정 횟수
- ScheduleIssue 발생 수
- RelaxationProposal 승인율
- 휴가/조합/휴식 관련 override 빈도
- 확정까지 걸린 재계산 횟수
- 엑셀 다운로드 횟수
- 같은 조직의 반복 사용 여부
- 관리자 만족도 또는 피드백 메모

제품 메시지는 다음 가치를 중심으로 검증합니다.

- 기존 Excel 작성 시간 감소
- 예외 조율 과정의 기록화
- 공정성 설명 가능성 향상
- 민감 정보의 LLM 비전송

기준선 수집:

- 온보딩 중 `기존 방식으로 근무표 1건 작성에 걸리는 평균 시간`을 1문항으로 수집합니다.
- 첫 생성 완료 후 실제 생성 시간과 수동 수정 횟수를 함께 기록합니다.
- 반복 사용 조직은 이전 ScheduleRun 대비 생성 시간, 이슈 수, 승인 수 변화를 비교합니다.

## 19. 테스트 전략

### Solver 테스트 (1차 필수)

- 작은 인원으로 해가 명확한 golden case를 작성합니다.
- 휴가자 제외, 상극 조합 제외, 역할 자격 제외를 각각 검증합니다.
- 높은 미배정 손실 또는 승인 필요 충돌이 있는 입력에서 완화안이 생성되는지 검증합니다.
- 같은 입력과 seed에서 재현성 우선 모드 결과가 반복되는지 검증합니다.

### API 테스트 (1차 필수)

- 조직 스코프가 다른 데이터에 접근할 수 없는지 검증합니다.
- ScheduleRun 상태 전이를 검증합니다.
- SchedulePublication 생성과 기간 중복 방지를 검증합니다.
- 미배정 요구사항이 ScheduleIssue로 저장되는지 검증합니다.
- 예외 승인 후 재계산 흐름을 검증합니다.
- 같은 idempotency key와 같은 snapshot hash 요청이 기존 ScheduleRun을 반환하는지 검증합니다.
- 같은 idempotency key와 다른 snapshot hash 요청이 `409 Conflict`를 반환하는지 검증합니다.
- worker retry 시 이전 attempt의 partial Assignment, ScheduleIssue, SolverDiagnosticEvent가 정리되거나 비활성화되는지 검증합니다.
- 수동 수정 Assignment가 재계산 후에도 유지되는지 검증합니다.
- 최대 재계산 라운드 초과 시 manual review issue가 생성되는지 검증합니다.

### DB 테스트 (1차 필수)

- PairConstraint가 employee 순서와 무관하게 정규화되고 중복 저장되지 않는지 검증합니다.
- 같은 ScheduleRun/slot에서 같은 직원이 여러 역할에 배정되지 않는지 검증합니다.
- active SchedulePublication의 완전 동일 기간과 일부 겹침 기간이 모두 막히는지 검증합니다.
- 자식 테이블 organization_id가 부모와 불일치할 때 저장이 실패하는지 검증합니다.

### 엑셀 테스트 (v1)

- 정상 템플릿 업로드를 검증합니다.
- 필수 컬럼 누락, 잘못된 직원 코드, 잘못된 날짜 형식을 검증합니다.
- upsert와 replace 모드를 각각 검증합니다.

### Bulk paste 테스트 (1차 필수)

- 직원 bulk paste의 필수 컬럼 누락, 중복 employee_code, 잘못된 roles 값을 검증합니다.
- 불가 일정 bulk paste의 잘못된 날짜 형식과 종료가 시작보다 빠른 입력을 검증합니다.
- 조합 제한 bulk paste의 자기 자신 조합과 중복 역순 입력을 검증합니다.
- 오류가 행 번호, 컬럼명, 사유로 표시되는지 검증합니다.

### Frontend 테스트 (1차 필수)

- ScheduleRun 상태별 렌더링을 검증합니다.
- `feasible_not_proven_optimal` 결과에서 `최적 보장 없음` 배지가 표시되는지 검증합니다.
- 수동 수정 후 validation error가 표시되는지 검증합니다.
- 묶음 완화안이 1차 UI에서 읽기 전용이며 수동 조정 폴백을 제공하는지 검증합니다.
- published 상태에서 그리드가 read-only로 표시되는지 검증합니다.

### LLM 테스트 (1차 필수)

- 익명화 payload에 실명과 조직명이 포함되지 않는지 검증합니다.
- LLM payload에 numeric loss score가 포함되지 않는지 검증합니다.
- LLM이 만든 문장이 원본 완화안의 type을 왜곡하지 않는지 검증합니다.
- LLM 응답이 JSON schema를 위반하면 fallback 문구를 사용하는지 검증합니다.
- reason code 왜곡, proposal type 왜곡, 개인정보 누출이 0건인지 golden set으로 검증합니다.

## 20. 주요 리스크

### 제약 모델 과복잡화

처음부터 모든 회사의 모든 근무 규칙을 지원하려고 하면 구현이 커집니다. 기본 정책과 고급 설정을 분리하고, 초기 완성 범위에서는 가장 일반적인 제약부터 구현해야 합니다.

### 승인 가능 제약 모델링 난이도

절대 불가 제약과 승인 시 완화 가능 제약을 섞으면 구현이 모순됩니다. 따라서 1차 엄격 생성과 실패 진단 모델을 분리하고, 승인 가능 제약에만 assumption 또는 enforcement literal을 사용합니다.

### 재현성과 성능의 충돌

CP-SAT는 병렬 검색 worker를 쓰면 더 빠를 수 있지만 재현성이 약해질 수 있습니다. 재현성 우선 모드는 `num_search_workers=1`과 고정 seed를 사용하고, 빠른 생성 모드는 성능을 우선합니다.

### 미배정과 충돌 상황의 설명 품질

solver 실패 결과를 바로 LLM에 넘기면 설명이 부정확해질 수 있습니다. 서버에서 후보 제거 로그, 진단 모델 결과, 완화안 랭킹을 먼저 만들고, LLM은 그 구조 데이터를 자연어로 바꾸는 역할만 해야 합니다.

### 개인정보 노출

직원명, 조직명, 휴가 상세 사유가 LLM으로 전송되면 SaaS 제품으로서 리스크가 큽니다. 익명화 계층은 필수 모듈로 분리해야 하며, 요청 단위 pseudonym과 최소 데이터 전송을 적용합니다.

### 멀티테넌시 격리 실패

애플리케이션 코드에서 `organization_id` 필터를 누락하면 다른 조직 데이터가 노출될 수 있습니다. PostgreSQL RLS를 함께 적용해 방어 계층을 늘립니다.

### Railway 리소스 제한

직원 100명, 긴 기간, 복잡한 제약에서는 solver 시간이 늘어날 수 있습니다. 생성 기간 제한, timeout, cancel, retry, worker 분리가 필요합니다.

## 21. 향후 확장

- 직원별 선호 근무 입력
- 조직별 승인 워크플로우
- 반복 생성 시 과거 근무표 반영 고도화
- Slack/메일 알림
- HR 시스템 연동
- 법정 근로시간 규칙 프리셋
- 다국어 지원
- 비용/요금제 기반 SaaS 확장

## 22. 참고 레퍼런스

- Google OR-Tools Employee Scheduling: https://developers.google.com/optimization/scheduling/employee_scheduling
- Google OR-Tools Scheduling Overview: https://developers.google.com/optimization/scheduling
- Google OR-Tools CP-SAT Solver: https://developers.google.com/optimization/cp/cp_solver
- OR-Tools Python CP-SAT API: https://or-tools.github.io/docs/pdoc/ortools/sat/python/cp_model.html
- Timefold Employee Shift Scheduling Constraints: https://docs.timefold.ai/employee-shift-scheduling/latest/user-guide/constraints
- Timefold Interpreting Model Run Results: https://docs.timefold.ai/timefold-platform/latest/how-tos/interpreting-model-run-results
- Timefold Constraint and Score Overview: https://docs.timefold.ai/timefold-solver/latest/constraints-and-score/overview
- Railway FastAPI Deployment Guide: https://docs.railway.com/guides/fastapi
- Railway Cron, Workers, and Queues Guide: https://docs.railway.com/guides/cron-workers-queues
- FastAPI Background Tasks: https://fastapi.tiangolo.com/tutorial/background-tasks/
- PostgreSQL Row Security Policies: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- RFC 5545 iCalendar: https://datatracker.ietf.org/doc/html/rfc5545
