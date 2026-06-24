# Decisions

## 2026-06-24

- 직원 bulk paste API를 별도 `employees.py` 라우터로 둡니다. 조직 API 파일에 추가하면 곧 휴가/조합 제한 입력까지 섞일 가능성이 있어 파일 책임이 흐려집니다.
- 이번 단계에서는 `active` 입력을 구현하지 않습니다. 현재 M0 OpenAPI의 `EmployeeBulkPasteRow` 필수/속성은 `row_no`, `employee_code`, `name`, `role_names`, `max_shifts_per_week`입니다.
- 오류가 하나라도 있으면 부분 저장하지 않습니다. paste 입력은 관리자가 한 번에 붙여넣는 작업이므로 부분 성공보다 수정 가능한 검증 결과가 안전합니다.
- `validate_only` 응답의 `employees`는 빈 배열로 둡니다. 아직 UI preview 계약이 구체화되지 않았고, M0 계약은 결과 배열 존재만 요구합니다.
