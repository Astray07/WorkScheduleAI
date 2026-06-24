# Release Feedback Hardening Plan

- [x] 리뷰 피드백을 코드와 대조합니다.
- [x] 범위와 성공 기준을 기록합니다.
- [x] RED 테스트를 추가하고 실패를 확인합니다.
- [x] published run 재계산 잠금을 구현합니다.
- [x] slot/employee 단위 휴가 override와 원인 기반 proposal을 구현합니다.
- [x] manual edit validation API를 구현합니다.
- [x] snapshot에 생성 slot/requirement를 추가합니다.
- [x] PostgreSQL RLS migration과 tenant context hook을 추가합니다.
- [x] focused/full verification을 실행합니다.
- [x] 문서를 갱신하고 커밋합니다.

## 검증 방법

- `python -m pytest tests\api\test_schedule_runs_api.py -q`
- `python -m pytest tests\api\test_p0_vertical_slice_api.py -q`
- `python -m pytest tests\db\test_alembic_migrations.py -q`
- `python -m pytest -q`
- `cd frontend; npm run build`
- `git diff --check`
