# Decisions

## 1. 서비스 형태

SaaS형 구조로 진행합니다. 여러 회사가 각자 데이터를 분리해서 사용할 수 있도록 `organization_id` 중심의 멀티테넌트 구조를 전제로 합니다.

## 2. 근무 단위

기본은 `사수 1명 + 부사수 1명`이지만, 회사별로 역할명과 역할별 필요 인원 수를 설정할 수 있게 합니다. 하루 1근무, 시간대별 근무, 당직/비상근무는 템플릿으로 제공합니다.

## 3. 입력 방식

화면 입력과 엑셀 업로드/다운로드를 모두 지원합니다. 기존 회사 자료가 엑셀일 가능성이 높기 때문입니다.

## 4. AI 구조

근무표 생성은 LLM이 아니라 OR-Tools 기반 제약 최적화 엔진이 담당합니다. LLM은 충돌 원인 요약, 완화안 설명, 관리자용 자연어 설명에만 사용합니다.

## 5. 개인정보 보호

LLM에는 직원 실명, 조직명, 휴가 상세 사유, 상극 관계 실명 정보를 보내지 않습니다. 익명화된 ID와 제약 유형만 전달합니다.

## 6. 최소 손실 추천

기본 제약은 엄격하게 지키되, 해가 없으면 시스템이 자동으로 제약을 깨지 않고 관리자에게 최소 손실 완화안을 추천합니다. 기본 손실 정책을 제공하고, 고급 설정에서 조직별 가중치를 조정할 수 있게 합니다.

## 7. 제약 분류 수정

피드백을 반영해 제약을 `필수/준필수/최적화`가 아니라 `절대 불가/승인 시 완화 가능/점수 기반 최적화`로 재분류했습니다. 휴가, 출장, 개인 일정, 상극 조합은 1차 생성에서는 지키지만, 해가 없을 때 관리자에게 완화 후보로 제시할 수 있는 승인 필요 제약으로 둡니다.

## 8. 실패 진단 전략

CP-SAT 실패 결과만으로 설명을 만들지 않습니다. solver 실행 전 후보 제거 로그를 만들고, 실패 시 승인 가능 제약에 assumption 또는 enforcement literal을 붙인 진단 모델을 실행합니다. 이 결과는 완화안 후보 생성에 사용하되, 전역 최소라고 가정하지 않고 서버 랭킹 레이어에서 다시 정렬합니다.

## 9. 범위 단계화

피드백을 반영해 MVP, v1, v2 범위를 표로 분리했습니다. 실제 구현 착수 기준은 별도의 `1차 완성 범위` 표로 확정했으며, 1차에는 bulk paste, 단일 완화안 승인, 비동기 LLM 설명 fallback, 엑셀 다운로드를 포함합니다. 정식 엑셀 업로드, 일반 사용자 기능, 고급 정책 UI는 단계적으로 확장합니다.

## 10. 재현성과 worker 분리

ScheduleRun에 입력 snapshot, model/solver version, OR-Tools version, random_seed, num_search_workers, timeout, objective score breakdown을 저장하도록 했습니다. CPU-bound solver 실행은 FastAPI 요청 내부가 아니라 Railway의 별도 worker 서비스에서 처리하는 방향으로 정했습니다.

## 11. 미배정과 확정본 모델 분리

필요 역할/필요 인원 미충족은 soft penalty로 분류했습니다. 직원이 배정되지 않은 결과는 Assignment에 억지로 넣지 않고 ScheduleIssue로 저장합니다. ScheduleRun은 실행 기록으로만 두고, 최종 확정본은 SchedulePublication으로 분리했습니다.

## 12. 연속근무와 최소휴식 위치

연속근무 제한과 최소휴식 시간은 점수 기반 soft 제약이 아니라 승인 시 완화 가능 제약으로 통일했습니다. 1차 엄격 생성에서는 지키고, 해가 없을 때만 인스턴스 단위 완화안으로 제시합니다.

## 13. 완화안 입도와 묶음 승인

완화안은 제약 종류 전체가 아니라 인스턴스 단위로 생성합니다. 예를 들어 휴가 완화는 `(employee, slot)`, 조합 완화는 `(employee_a, employee_b, slot)`, 미배정 완화는 `(slot, role, missing_count)` 단위입니다. 여러 완화안이 함께 필요하면 RelaxationProposal에 group_id와 requires_proposal_ids를 둡니다.

## 14. RLS 전략

RLS 정책을 단순하게 유지하기 위해 tenant 데이터가 있는 자식/조인 테이블에도 organization_id를 비정규화해 저장합니다. DB session에는 app.current_organization_id를 설정하고, RLS와 애플리케이션 레벨 organization scope를 함께 적용합니다.

## 15. 미배정 분류 최종 결정

필요 역할/필요 인원 미충족은 승인 필요 hard 제약이 아니라 1차 solver objective의 soft penalty로 둡니다. 미배정 결과는 ScheduleIssue로 저장하고, 미배정 손실을 줄일 수 있는 휴가/조합/휴식 완화 후보를 관리자에게 제안합니다.

## 16. 역할별 미배정 가중치

커스텀 역할을 지원하므로 특정 기본 역할에 고정된 미배정 가중치 필드는 사용하지 않고, `SchedulePolicyRoleWeight`와 `ShiftRequirement.unfilled_weight_override`로 역할별 미배정 손실을 표현합니다.

## 17. 확정본 불변성과 승인 대상 확장

SchedulePublication은 발행된 Assignment/ScheduleIssue를 불변으로 취급합니다. OverrideApproval은 `relaxation_proposal_id`, `proposal_group_id`, `target_json`을 통해 미배정 허용, 역할 인원 축소, 묶음 완화 승인까지 표현합니다.

## 18. 1차 완성 범위 재정의

다관점 피드백을 반영해 1차 완성 범위를 별도 표로 확정했습니다. 1차는 P0 vertical slice, bulk paste 입력, 단일 완화안 승인, LLM 설명 fallback, 엑셀 다운로드까지 포함하고, 정식 엑셀 업로드, 묶음 완화안 승인 UI, 고급 정책 UI, 일반 사용자 기능은 후속으로 둡니다.

## 19. 계약 우선 구현

OpenAPI 초안, ScheduleRun 상태 머신, 핵심 API 응답 형태, UI acceptance criteria, DB invariant, worker idempotency를 기획서에 추가했습니다. 구현 계획은 이 계약을 기준으로 작성합니다.

## 20. LLM 운영 원칙

LLM은 생성 경로를 막지 않는 비동기 설명 레이어로 둡니다. 구조화 JSON schema, 금지 표현, fallback template, eval set, 개인정보 누출 테스트를 요구사항으로 추가했습니다.

## 21. HR 도입 기준

정식 엑셀 업로드를 후속으로 두는 대신 1차에 bulk paste 입력을 넣었습니다. 휴가 override 수동 통지 체크, 법적 보증 아님 안내, Excel 다운로드, 도입 성공 지표를 추가했습니다.

## 22. 확정/재계산 워크플로우 최종 정리

최소 SchedulePublication은 1차 완성 범위에 포함합니다. 검토 완료된 결과는 발행되어 read-only로 잠깁니다. 승인 후 재계산은 같은 ScheduleRun에서 recalculation_count를 증가시키며 수행하고, 승인된 override와 locked_by_user 수동 배정은 고정 제약으로 유지합니다. 최대 재계산 라운드는 3회로 제한합니다.

## 23. API와 테스트 보강

결과 그리드 렌더링을 위해 `GET /schedule-runs/{id}/result` payload를 추가했습니다. 동일 슬롯 동일 직원 중복 배정을 막는 DB invariant, idempotency key 충돌 처리, retry cleanup, bulk paste, frontend 상태 렌더링, LLM schema fallback 테스트를 추가했습니다.

## 24. 최종 검토 반영

테스트 전략을 `1차 필수`, `v1`로 태깅했습니다. LLM output contract에 enum과 길이 제한을 추가했습니다. 1차에서는 같은 조직의 active SchedulePublication 기간이 일부라도 겹치면 막습니다. 1차 tenant UX는 가입 사용자 1명당 조직 1개 관리이며 organization switcher는 만들지 않습니다. 데모 데이터 기준을 직원 4명, 1주 근무표, 휴가 1건, 상극 조합 1건, 완화안 케이스 1건으로 고정했습니다. `current_attempt_no`는 worker 기술 재시도, `recalculation_count`는 관리자 승인/수동 변경 기반 재계산 라운드로 분리했습니다.

## 25. 1차 릴리즈 인원 기준

1차 릴리즈의 권장 직원 수와 성능 보장 기준을 2-50명으로 상향했습니다. 최종 목표인 100명 지원은 유지하되, 100명/31일 안정 성능 최적화는 후속 hardening 범위로 둡니다.
