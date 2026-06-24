# Verification

## 수행한 확인

- 저장소가 비어 있고 Git 저장소가 아직 초기화되지 않은 상태임을 확인했습니다.
- OR-Tools 직원 스케줄링 문서에서 CP-SAT 기반 직원 스케줄링 예제를 확인했습니다.
- Timefold 문서에서 hard, medium, soft constraint와 score 기반 해석 방식을 확인했습니다.
- Railway FastAPI 배포 문서에서 FastAPI 앱 배포 방식을 확인했습니다.
- 사용자와 대화에서 확정한 조건을 기획서에 반영했는지 자체 점검했습니다.
- 피드백 반영 시 OR-Tools CP-SAT API 문서에서 assumption, random_seed 관련 API가 있음을 확인했습니다.
- Railway worker/queue 문서에서 장시간 계산은 별도 worker 또는 queue로 분리하는 구성을 확인했습니다.
- FastAPI BackgroundTasks 문서에서 무거운 background computation은 Celery 같은 외부 도구가 유리하다는 caveat를 확인했습니다.
- PostgreSQL RLS 공식 문서에서 row security policy를 테이블/명령/역할 단위로 적용할 수 있음을 확인했습니다.
- 2차 피드백을 반영해 미배정, 연속근무/최소휴식, 진단 이벤트, 확정 근무표 모델, RLS 자식 테이블 전략을 문서에 추가했습니다.
- 최종 피드백을 반영해 미배정은 soft penalty로 이동하고, 역할별 미배정 가중치와 OverrideApproval 확장 필드, SchedulePublication 불변성, 성공 기준 분리를 추가했습니다.
- 다관점 피드백을 반영해 1차 완성 범위, P0 vertical slice, API contract sketch, UI acceptance criteria, DB invariant, worker idempotency, LLM output contract/eval/fallback, HR 도입 지표와 온보딩 흐름을 추가했습니다.
- 2차 다관점 피드백을 반영해 SchedulePublication을 1차에 포함하고, LLM 단계 문구, 1주 P0/31일 릴리즈 제한, result payload, assignment unique invariant, 재계산/수동수정 규칙, attempt_no, 테스트 전략을 수정했습니다.
- 최종 검토를 반영해 테스트 전략 단계 태그, LLM schema enum/길이 제한, SchedulePublication overlap 의미, 단일 tenant UX, Railway demo data, attempt_no/recalculation_count 의미 분리를 추가했습니다.
- 1차 릴리즈 권장 직원 수와 성능 보장 기준을 30명에서 50명으로 상향했는지 문서 검색으로 확인했습니다.

## 결과

- 메인 기획서 파일을 작성하고 피드백을 반영해 수정했습니다.
- 구현이나 테스트 실행은 수행하지 않았습니다. 현재 단계가 기획 문서 작성이기 때문입니다.

## 남은 위험

- 실제 구현 단계에서는 OR-Tools assumption 기반 진단 모델과 solver timeout 정책을 별도로 검증해야 합니다.
- 엑셀 템플릿의 구체 컬럼은 구현 계획 단계에서 확정해야 합니다.
- Railway 배포 구성은 실제 프로젝트 스택 확정 후 API/worker/Redis/PostgreSQL 단위로 다시 검증해야 합니다.
- RLS 비정규화 필드와 FK 일관성은 DB 스키마 설계 단계에서 마이그레이션과 테스트로 검증해야 합니다.
- soft penalty 기반 미배정 objective는 solver MVP 단계에서 golden case로 검증해야 합니다.
- OpenAPI, DB migration, UI 구현 계획은 이번 기획서의 contract sketch를 기준으로 별도 상세화해야 합니다.
- 재계산 루프 제한과 수동 배정 lock 동작은 solver MVP 단계에서 실제 golden case로 검증해야 합니다.
- publication 기간 겹침과 attempt/recalculation 분리는 DB migration/API 테스트 단계에서 검증해야 합니다.
- 50명/31일 기준 solver 성능은 구현 단계의 benchmark 또는 golden/performance case로 별도 검증해야 합니다.
