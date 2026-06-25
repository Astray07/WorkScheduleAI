# XLSX Import Contract

확인일: 2026-06-25

## Request Contract

Existing CSV/TSV import remains supported:

```json
{
  "type": "employees",
  "format": "delimited",
  "content": "employee_code,name,roles,max_shifts_per_week\nE001,Kim,사수,5"
}
```

Official `.xlsx` import uses the same preview/apply endpoints with base64 workbook content:

```json
{
  "type": "employees",
  "format": "xlsx",
  "content_base64": "<base64 .xlsx bytes>",
  "sheet_name": "employees"
}
```

If `sheet_name` is omitted, the backend uses the `type` value as the sheet name. Apply uses the same body plus `"mode": "upsert"`.

## Error Contract

Preview returns HTTP 200 for row validation errors and blocks apply when `valid` is `false`.

`.xlsx` row errors include:

- `sheet`: worksheet name.
- `row_no`: actual spreadsheet row number. Header is row 1, first data row is row 2.
- `column`: source column name.
- `code`: stable error code.
- `message`: operator-facing validation message.

CSV/TSV errors preserve the legacy `field` and `row_no` shape.

## Sheet Contracts

### `employees`

| Column | Required value | Notes |
| --- | --- | --- |
| `employee_code` | yes | Natural key for upsert. |
| `name` | yes | Employee display name. |
| `roles` | yes | Existing role names separated by `|` or `;`. |
| `max_shifts_per_week` | no | Integer `0..31`; blank stores no employee-specific cap. |

Apply upserts by `(organization_id, employee_code)` and replaces role eligibility links for that employee.

### `unavailabilities`

| Column | Required value | Notes |
| --- | --- | --- |
| `employee_code` | yes | Must already exist in the organization. |
| `type` | yes | `vacation`, `business_trip`, `training`, or `personal`. |
| `starts_at` | yes | ISO datetime, for example `2026-07-01T00:00:00+09:00`. |
| `ends_at` | yes | ISO datetime after `starts_at`. |
| `override_allowed` | yes | `true/false`, `1/0`, `yes/no`, `허용/불가`. |

Apply inserts rows. Repeated imports can create repeated unavailability records.

### `pair_constraints`

| Column | Required value | Notes |
| --- | --- | --- |
| `employee_code_a` | yes | Must already exist. |
| `employee_code_b` | yes | Must already exist and differ from employee A. |
| `type` | yes | `blocked`, `avoid`, or `prefer`. |
| `severity` | yes | `low`, `medium`, `high`, or `critical`. |
| `override_allowed` | yes | `true/false`, `1/0`, `yes/no`, `허용/불가`. |

Apply upserts by normalized employee pair plus constraint type.

### `shift_types`

| Column | Required value | Notes |
| --- | --- | --- |
| `shift_type` | yes | Natural key for shift type upsert. |
| `local_start_time` | yes | `HH:MM`, 24-hour time. |
| `local_end_time` | yes | `HH:MM`, must differ from start time. |
| `timezone` | yes | Example: `Asia/Seoul`. |
| `crosses_midnight` | yes | `true/false`, `1/0`, `yes/no`, `허용/불가`. |
| `active_weekdays` | yes | Unique weekday integers `0..6`, separated by `|`, `;`, or `,`. Monday is `0`. |
| `active` | yes | `true/false`, `1/0`, `yes/no`, `허용/불가`. |
| `role_name` | yes | Existing role name. |
| `required_count` | yes | Integer `1..20`. |
| `unfilled_weight_override` | no | Integer `0..10000`; blank uses policy default. |

Each row defines one role requirement for the shift type. Apply upserts by `(organization_id, shift_type)` and replaces all requirements for each imported shift type.

### `policy`

| Column | Required value | Notes |
| --- | --- | --- |
| `key` | yes | Existing schedule policy field. |
| `value` | yes | Value validated by field-specific contract. |

Supported keys are the fields exposed by the schedule policy API, including `name`, `min_rest_hours`, `max_consecutive_shifts`, `max_shifts_per_week`, weekend/night monthly caps, unfilled penalty weight, workload fairness weight, pair avoid weight, and `unfilled_policy`.

## Scope Notes

- The first official `.xlsx` path previews and applies one selected sheet per request.
- Cross-sheet dependency resolution inside one workbook is intentionally not implemented in this slice. Import employees before sheets that reference employee codes.
- Formula evaluation, merged cells, and Excel serial date conversion are not supported. Date/time import cells should contain text in the documented formats.
