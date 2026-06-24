# First Release Execution Brief

## 목표

WorkScheduleAI를 현재 P0 backend API 상태에서 1차 릴리즈 후보까지 단계적으로 구현합니다.

## 비목표

- 정식 Excel 업로드는 구현하지 않습니다.
- 고급 정책 UI, 결제, 일반 사용자 조회, 조직 초대는 구현하지 않습니다.
- 100명/31일 안정 성능 최적화는 hardening 범위로 둡니다.
- LLM이 스케줄 결정을 하도록 만들지 않습니다.

## 성공 기준

- 직원 2-50명, 최대 31일 생성 흐름을 API/UI에서 사용할 수 있습니다.
- P0 vertical slice를 브라우저에서 시연할 수 있습니다.
- OR-Tools 또는 명시된 solver 인터페이스가 근무표를 생성합니다.
- LLM 설명은 설명 레이어이며, 개인정보를 보내지 않고 fallback이 동작합니다.
- ScheduleRun과 SchedulePublication이 분리됩니다.
- Excel 다운로드와 Railway 배포 산출물이 준비됩니다.

## 제약

- 질문 없이 합리적 가정으로 진행합니다.
- 각 증분은 TDD로 시작하고 검증 후 커밋합니다.
- 작업 상태는 이 디렉터리와 각 하위 작업 디렉터리에 유지합니다.
