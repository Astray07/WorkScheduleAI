# Release Feedback Remediation Plan

- [x] 리뷰 피드백을 읽고 코드 상태와 대조합니다.
- [x] 범위와 성공 기준을 정리합니다.
- [x] 실패 테스트를 추가합니다.
- [x] 결과 artifact 영속 모델과 migration을 추가합니다.
- [x] worker 실행 경로가 artifact를 계산/저장하도록 수정합니다.
- [x] result/publication/excel이 저장본을 사용하도록 수정합니다.
- [x] snapshot/idempotency와 frontend shift template 흐름을 보강합니다.
- [x] PostgreSQL deploy dependency를 추가합니다.
- [x] focused/full verification을 실행합니다.
- [x] 문서를 갱신하고 커밋합니다.

## 검증 방법

- `python -m pytest tests\api\test_schedule_runs_api.py -q`
- `python -m pytest tests\api\test_p0_vertical_slice_api.py -q`
- `python -m pytest tests\worker\test_schedule_worker.py -q`
- `python -m pytest tests\scripts\test_seed_demo.py -q`
- `python -m pytest -q`
- `cd frontend; npm run build`
- browser P0 flow smoke: FastAPI/Vite 로컬 실행 후 Playwright로 P0 생성, 승인, 재계산, 확정, 다운로드 버튼 확인
- `git diff --check`
