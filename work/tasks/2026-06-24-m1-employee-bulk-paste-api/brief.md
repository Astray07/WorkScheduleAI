# Brief

## 목표

P0 vertical slice의 직원 4명 입력 단계를 위해 `POST /organizations/{organization_id}/employees/bulk-paste` API를 구현합니다.

## 비목표

- 정식 `.xlsx` 업로드 구현
- 직원 관리 전체 CRUD 구현
- 인증, 멤버십, tenant context 적용
- 휴가, 조합 제한, solver 구현

## 성공 기준

- `validate_only`는 유효성만 검사하고 DB에 직원을 저장하지 않습니다.
- `upsert`는 `employee_code` 기준으로 직원을 생성하거나 갱신합니다.
- payload 내부 중복 `employee_code`와 알 수 없는 `role_names`는 행 번호, 필드, 코드로 반환합니다.
- 오류가 있으면 부분 저장하지 않습니다.
- 기존 전체 테스트가 계속 통과합니다.

## 제약과 가정

- 1차 릴리즈 기준 직원 수는 2-50명이며, 계약상 bulk paste 입력은 최대 100행입니다.
- 역할은 같은 조직의 `roles.name`으로 매칭합니다.
- `active` 컬럼은 계약 초안의 행 스키마에는 없으므로 이번 API에서는 생성/갱신 모두 `true`를 유지합니다.
- 이번 작업은 OR-Tools/LLM 경로와 무관한 기준정보 입력 계약 고정입니다.
