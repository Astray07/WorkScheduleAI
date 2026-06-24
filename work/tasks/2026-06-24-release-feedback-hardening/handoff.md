# Release Feedback Hardening Handoff

## 현재 상태

2차 리뷰 피드백의 P0/P1 API hardening과 PostgreSQL RLS baseline을 구현했습니다.

- 발행된 ScheduleRun은 재계산할 수 없습니다.
- 휴가 override는 proposal이 가리키는 employee/slot에만 적용됩니다.
- 휴가 원인 후보가 없는 미배정은 `mark_manual_review` proposal로 표시됩니다.
- manual edit validation endpoint가 추가됐습니다.
- ScheduleInputSnapshot에 생성 slot/requirement 목록이 포함됩니다.
- Alembic revision `20260624_0009`가 PostgreSQL tenant RLS 정책을 추가합니다.
- `get_db_session`은 organization path param을 `SET LOCAL app.current_organization_id`로 설정합니다.

## 다음 단계

1. 관련 파일만 stage/commit합니다.
2. 기존 unstaged review 문서와 `docs/.bkit-memory.json`은 건드리지 않습니다.
3. 후속 작업으로 실제 PostgreSQL RLS end-to-end 검증, Redis worker 분리, 고급 진단 모델을 별도 계획으로 진행합니다.
