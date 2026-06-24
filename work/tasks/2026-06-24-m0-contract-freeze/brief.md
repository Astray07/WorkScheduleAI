# Brief

## 목표

WorkScheduleAI M0 계약 고정 산출물을 작성합니다. M0는 OpenAPI 초안, ScheduleRun 상태 머신, 핵심 enum/schema, DB migration 계획, mock 결과 UI fixture를 고정해 API, worker, frontend가 병렬 개발을 시작할 수 있는 상태를 만드는 단계입니다.

## 비목표

- 실제 FastAPI, React/Next.js, worker, solver 구현은 시작하지 않습니다.
- OR-Tools 모델링과 성능 최적화는 M2 이후로 둡니다.
- 실제 Alembic migration 파일은 애플리케이션 스캐폴딩 이후 작성합니다.
- 100명/31일 안정 성능 hardening은 후속 범위로 둡니다.

## 성공 기준

- P0 vertical slice에 필요한 API 계약이 OpenAPI JSON으로 문서화됩니다.
- ScheduleRun 상태 전이와 `current_attempt_no`/`recalculation_count` 분리가 명확합니다.
- 핵심 enum과 response schema가 mock UI 구현에 충분합니다.
- DB migration 순서, 핵심 invariant, RLS 적용 방향이 문서화됩니다.
- issue path와 recalculation 후 결과를 표현하는 mock fixture가 JSON으로 제공됩니다.
- JSON 산출물은 파싱 검증을 통과합니다.

## 제약

- 응답과 작업 문서는 존댓말 기조를 유지합니다.
- M0 범위를 넘는 실제 앱 스캐폴딩은 하지 않습니다.
- 미배정은 hard 제약이 아니라 soft penalty 결과로 `ScheduleIssue`에 표현합니다.
- LLM은 설명 레이어이며, 근무표나 완화안을 생성하지 않습니다.
- LLM payload에는 개인정보를 보내지 않는 전제를 계약 문서에 남깁니다.
- ScheduleRun 실행 기록과 SchedulePublication 확정본은 분리합니다.
- 재계산은 override/manual lock을 유지하고 `recalculation_count <= 3`으로 제한합니다.

