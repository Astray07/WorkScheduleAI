# Brief

## 목표

P0 vertical slice의 완화안 승인 단계를 위해 relaxation proposal 승인 API와 OverrideApproval 저장소를 구현합니다.

## 비목표

- 재계산 API
- 실제 RelaxationProposal DB 테이블
- OR-Tools 재실행
- notification 발송
- 감사 로그 고도화

## 성공 기준

- mock proposal `proposal_mock_time_off_1`을 승인하면 OverrideApproval이 저장됩니다.
- 승인만으로 `recalculation_count`는 증가하지 않습니다.
- 같은 run/proposal 중복 승인은 409로 거부합니다.
- 승인 후 result API는 해당 proposal status를 `approved`로 반환합니다.
- 기존 전체 테스트가 계속 통과합니다.

## 제약과 가정

- 이번 단계의 proposal 원본은 ScheduleRun mock result builder에서 생성합니다.
- 승인 기록은 다음 재계산 API에서 고정 제약으로 사용할 수 있도록 DB에 저장합니다.
- notification은 `notification_required` 값만 저장하고 실제 발송/기록자는 후속 범위입니다.
