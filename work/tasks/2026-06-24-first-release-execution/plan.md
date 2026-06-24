# First Release Execution Plan

- [x] 현재 저장소와 기획서의 1차 범위를 대조합니다.
- [x] 1차 릴리즈 상위 실행 계획을 작성합니다.
- [x] ShiftType/ShiftRequirement 모델과 API를 구현합니다.
- [x] OR-Tools solver MVP를 구현합니다.
- [x] ScheduleRun worker 상태 전이를 보강합니다.
- [x] P0 운영형 프론트엔드를 구현합니다.
- [x] LLM 설명 fallback/privacy 테스트를 구현합니다.
- [x] Railway 배포 산출물과 데모 seed를 준비합니다.

## 검증 방법

- 각 하위 작업의 focused pytest
- `python -m pytest -q`
- frontend 구현 후 browser/screenshot 검증
- deployment smoke command 검증
