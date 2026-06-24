# M1 Shift Template API Plan

- [x] 범위와 성공 기준을 정리합니다.
- [x] 실패 테스트를 작성하고 RED를 확인합니다.
- [x] `ShiftType`, `ShiftRequirement` 모델과 migration을 추가합니다.
- [x] shift template 생성/조회 API를 추가합니다.
- [x] focused test와 전체 test를 실행합니다.
- [x] 변경을 커밋합니다.

## 검증 방법

- `python -m pytest tests/db/test_domain_models.py tests/db/test_alembic_migrations.py tests/api/test_shift_templates_api.py -q`
- `python -m pytest -q`
- `git diff --check`
