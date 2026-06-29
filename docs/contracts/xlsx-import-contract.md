# XLSX 가져오기 계약

확인일: 2026-06-25

## 요청 계약

기존 CSV/TSV 가져오기는 계속 지원합니다.

```json
{
  "type": "employees",
  "format": "delimited",
  "content": "employee_code,name,roles,max_shifts_per_week\nE001,Kim,사수,5"
}
```

공식 `.xlsx` 가져오기는 같은 preview/apply endpoint를 사용하고, workbook 내용을 base64로 전달합니다.

```json
{
  "type": "employees",
  "format": "xlsx",
  "content_base64": "<base64 .xlsx bytes>",
  "sheet_name": "employees"
}
```

`sheet_name`을 생략하면 backend는 `type` 값을 sheet 이름으로 사용합니다. Apply 요청은 같은 body에 `"mode": "upsert"`를 추가합니다.

## 오류 계약

Preview는 행 단위 validation 오류가 있어도 HTTP 200을 반환합니다. 단, `valid`가 `false`이면 apply는 차단됩니다.

`.xlsx` 행 오류에는 다음 필드가 포함됩니다.

- `sheet`: worksheet 이름
- `row_no`: 실제 spreadsheet 행 번호. header는 1행, 첫 데이터는 2행입니다.
- `column`: 원본 column 이름
- `code`: 안정적인 오류 코드
- `message`: 운영자가 읽을 수 있는 validation 메시지

CSV/TSV 오류는 기존 `field`, `row_no` 형태를 유지합니다.

## 시트 계약

### `employees`

| Column | 필수 | 설명 |
| --- | --- | --- |
| `employee_code` | yes | upsert 기준이 되는 직원 코드입니다. |
| `name` | yes | 직원 표시 이름입니다. |
| `roles` | yes | 기존 역할 이름을 `|` 또는 `;`로 구분합니다. |
| `max_shifts_per_week` | no | `0..31` 정수입니다. 비우면 직원별 상한을 저장하지 않습니다. |

Apply는 `(organization_id, employee_code)` 기준으로 upsert하고, 해당 직원의 역할 가능 링크를 교체합니다.

### `unavailabilities`

| Column | 필수 | 설명 |
| --- | --- | --- |
| `employee_code` | yes | 같은 조직에 이미 존재해야 합니다. |
| `type` | yes | `vacation`, `business_trip`, `training`, `personal` 중 하나입니다. |
| `starts_at` | yes | ISO datetime입니다. 예: `2026-07-01T00:00:00+09:00` |
| `ends_at` | yes | `starts_at`보다 늦은 ISO datetime입니다. |
| `override_allowed` | yes | `true/false`, `1/0`, `yes/no`, `허용/불가`를 지원합니다. |

Apply는 행을 insert합니다. 같은 파일을 반복 적용하면 같은 근무 불가 일정이 중복 생성될 수 있습니다.

### `pair_constraints`

| Column | 필수 | 설명 |
| --- | --- | --- |
| `employee_code_a` | yes | 이미 존재해야 합니다. |
| `employee_code_b` | yes | 이미 존재해야 하며 직원 A와 달라야 합니다. |
| `type` | yes | `blocked`, `avoid`, `prefer` 중 하나입니다. |
| `severity` | yes | `low`, `medium`, `high`, `critical` 중 하나입니다. |
| `override_allowed` | yes | `true/false`, `1/0`, `yes/no`, `허용/불가`를 지원합니다. |

Apply는 정규화된 직원 쌍과 constraint type 기준으로 upsert합니다.

### `shift_types`

| Column | 필수 | 설명 |
| --- | --- | --- |
| `shift_type` | yes | shift type upsert 기준입니다. |
| `local_start_time` | yes | 24시간제 `HH:MM` 형식입니다. |
| `local_end_time` | yes | 24시간제 `HH:MM` 형식이며 시작 시간과 달라야 합니다. |
| `timezone` | yes | 예: `Asia/Seoul` |
| `crosses_midnight` | yes | `true/false`, `1/0`, `yes/no`, `허용/불가`를 지원합니다. |
| `active_weekdays` | yes | `0..6` weekday 정수를 `|`, `;`, `,`로 구분합니다. 월요일은 `0`입니다. |
| `active` | yes | `true/false`, `1/0`, `yes/no`, `허용/불가`를 지원합니다. |
| `role_name` | yes | 이미 존재하는 역할 이름입니다. |
| `required_count` | yes | `1..20` 정수입니다. |
| `unfilled_weight_override` | no | `0..10000` 정수입니다. 비우면 policy 기본값을 사용합니다. |

각 행은 shift type의 role requirement 하나를 정의합니다. Apply는 `(organization_id, shift_type)` 기준으로 upsert하고, 가져온 각 shift type의 requirement를 모두 교체합니다.

### `policy`

| Column | 필수 | 설명 |
| --- | --- | --- |
| `key` | yes | 기존 schedule policy field입니다. |
| `value` | yes | field별 계약으로 검증되는 값입니다. |

지원하는 key는 schedule policy API가 노출하는 field입니다. 예를 들면 `name`, `min_rest_hours`, `max_consecutive_shifts`, `max_shifts_per_week`, 주말/야간 월간 상한, unfilled penalty weight, workload fairness weight, pair avoid weight, `unfilled_policy`가 있습니다.

## 범위 메모

- 첫 공식 `.xlsx` 경로는 요청당 선택한 sheet 하나를 preview/apply합니다.
- 하나의 workbook 안에서 sheet 간 의존성을 자동 해소하지 않습니다. 직원 코드를 참조하는 sheet보다 `employees`를 먼저 가져와야 합니다.
- formula evaluation, merged cells, Excel serial date conversion은 지원하지 않습니다. 날짜/시간 cell은 문서화된 형식의 text로 입력해야 합니다.
