# ScheduleRun State Machine

## 상태

| 상태 | 의미 | 종료 상태 |
| --- | --- | --- |
| `queued` | API가 ScheduleRun과 snapshot을 만들고 worker queue에 등록한 상태 | 아니요 |
| `running` | worker가 입력 검증, 모델 구성, solver, 진단, 완화안 생성을 수행하는 상태 | 아니요 |
| `succeeded` | 배정 결과가 생성되고 결과 조회가 가능한 상태 | 예 |
| `infeasible` | hard/승인 필요 제약을 모두 만족하는 해가 없고, 이슈/완화안 진단이 생성된 상태 | 예 |
| `failed` | 시스템 오류, 모델 오류, worker 오류로 결과를 신뢰할 수 없는 상태 | 예 |
| `canceled` | 관리자 또는 시스템 요청으로 실행이 취소된 상태 | 예 |

## 허용 전이

| From | To | 트리거 |
| --- | --- | --- |
| `queued` | `running` | worker가 job을 claim합니다. |
| `queued` | `canceled` | worker 시작 전 취소 요청이 들어옵니다. |
| `running` | `succeeded` | solver가 사용 가능한 결과를 만들고 저장 검증을 통과합니다. |
| `running` | `infeasible` | solver/진단 모델이 미배정 또는 승인 필요 완화안만 남긴 상태로 종료합니다. |
| `running` | `failed` | 입력 snapshot 손상, 모델 구성 오류, DB 저장 실패, worker 예외가 발생합니다. |
| `running` | `canceled` | worker checkpoint에서 취소 상태를 확인하고 중단합니다. |
| `succeeded` | `running` | 승인된 완화안 또는 locked manual assignment를 반영해 관리자 재계산을 요청합니다. |
| `infeasible` | `running` | 승인된 완화안 또는 locked manual assignment를 반영해 관리자 재계산을 요청합니다. |

## 금지 전이

- `failed`에서 자동으로 `running`으로 돌아가지 않습니다. 새 worker 기술 재시도는 같은 run 안에서 `running` 중에만 수행합니다.
- `canceled`에서 다른 상태로 돌아가지 않습니다.
- 발행된 ScheduleRun은 재계산하지 않습니다. 변경이 필요하면 새 ScheduleRun을 생성합니다.

## 카운터 의미

### current_attempt_no

`current_attempt_no`는 worker 기술 재시도와 attempt별 산출물 구분을 위한 값입니다.

- worker가 같은 ScheduleRun을 다시 처리할 때 증가합니다.
- 관리자 재계산 라운드 한도를 소진하지 않습니다.
- `Assignment`, `ScheduleIssue`, `SolverDiagnosticEvent`, `RelaxationProposal`은 attempt 번호를 저장합니다.
- 새 attempt를 시작하기 전에 이전 attempt의 partial 산출물은 비활성화하거나 attempt별로 분리해서 조회합니다.

### recalculation_count

`recalculation_count`는 관리자 승인 또는 수동 수정 이후 재계산 라운드입니다.

- `POST /relaxation-proposals/{proposal_id}/approve`만으로는 증가하지 않습니다.
- `POST /recalculate`가 승인된 override 또는 locked manual assignment를 반영해 solver를 다시 실행할 때 증가합니다.
- 1차 릴리즈 한도는 3회입니다.
- 3회를 초과하면 solver를 다시 실행하지 않고 `manual_review_required` ScheduleIssue를 생성합니다.

## 재계산 규칙

1. 승인된 `OverrideApproval`은 다음 solver 실행에서 고정 제약으로 반영합니다.
2. `locked_by_user = true`인 manual assignment는 다음 solver 실행에서 고정 배정으로 유지합니다.
3. 관리자가 잠금을 해제한 manual assignment만 solver가 변경할 수 있습니다.
4. 같은 ScheduleIssue와 같은 제약 조합이 반복되면 루프로 판단하고 자동 재계산을 중단합니다.
5. 묶음 완화안이 필요한데 1차 UI가 묶음 승인을 지원하지 않으면 읽기 전용으로 표시하고 수동 조정 또는 미배정 유지 폴백을 제공합니다.

## SchedulePublication 분리

ScheduleRun은 실행 기록이고 SchedulePublication은 확정본입니다.

- `POST /schedule-runs/{schedule_run_id}/publications`가 성공하면 result API는 `read_only: true`를 반환합니다.
- 발행된 ScheduleRun의 Assignment와 ScheduleIssue는 수정하지 않습니다.
- 같은 조직의 active publication 기간은 겹칠 수 없습니다.
- 겹침 기준은 `new.period_start < existing.period_end AND new.period_end > existing.period_start`입니다.

