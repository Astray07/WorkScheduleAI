# Decisions

## 2026-06-24

- 실제 `RelaxationProposal` 테이블은 아직 만들지 않습니다. proposal 원본은 solver/diagnostic 단계에서 확정해야 하며, 지금은 mock result 계약을 승인 대상으로 삼는 것이 더 작습니다.
- `OverrideApproval`은 중복 승인을 막기 위해 `(organization_id, schedule_run_id, relaxation_proposal_id)` unique constraint를 둡니다.
- 승인 API는 `recalculation_count`를 변경하지 않습니다. 상태 문서상 카운터 증가는 `POST /recalculate`의 책임입니다.
- 승인 후 result payload의 proposal status만 `approved`로 바꿉니다. assignments/issues는 재계산 전까지 그대로 둡니다.
