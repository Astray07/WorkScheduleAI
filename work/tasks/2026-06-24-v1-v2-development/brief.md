# V1/V2 Development Brief

## 목표

1차 릴리즈 완료 후보 이후 후속 범위인 v1/v2 개발을 제품 원칙과 기존 릴리즈 경계에 맞춰 순차적으로 진행합니다.

## 우선 순서

1. Redis worker 분리
2. 고급 진단/완화안 실제화
3. 수동 편집 저장/감사 이력
4. 100명/31일 성능 hardening
5. 운영 모니터링

## 비목표

- GitHub push, Railway/staging 배포, P0 수동 시나리오 검증은 마지막 통합 점검 전까지 수행하지 않습니다.
- 1차 릴리즈 범위와 무관한 대규모 리팩터링은 하지 않습니다.
- OR-Tools 외의 solver로 교체하지 않습니다.
- LLM이 근무표 생성 판단을 하도록 확장하지 않습니다.

## 성공 기준

- 각 단계는 테스트 우선 또는 최소한의 failing regression test 확인 후 구현합니다.
- 기존 1차 릴리즈 게이트인 `python -m pytest -q`, `frontend` build, `git diff --check`를 주요 통합 게이트로 유지합니다.
- Redis worker 분리 이후 API는 ScheduleRun을 생성하고 Redis job을 enqueue한 뒤 `queued` 상태를 반환하며, solver 실행은 별도 worker entrypoint에서 수행됩니다.
- 개인정보 익명화, ScheduleRun/SchedulePublication 분리, 미배정 ScheduleIssue 표현, recalculation_count 3회 제한을 유지합니다.

## 제약

- 현재 로컬 unstaged 변경인 `docs/.bkit-memory.json`과 `work/tasks/2026-06-24-product-plan-review/*` 리뷰/메모리 파일은 건드리지 않습니다.
- `AGENTS.md` 파일은 저장소에서 발견되지 않았으므로, 사용자 메시지에 포함된 AGENTS 지침을 작업 기준으로 적용합니다.
