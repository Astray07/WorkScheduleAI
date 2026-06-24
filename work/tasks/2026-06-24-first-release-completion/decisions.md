# First Release Completion Decisions

## 1. Redis worker는 1차 완료 blocking에서 제외

기획서는 Redis queue worker를 권장하지만, 현재 구현은 worker-compatible 함수 경계와 Railway worker command 문서를 이미 갖고 있습니다. 1차 릴리즈 완료 후보에서는 P0/직원 2-50명/31일 범위의 신뢰성과 검증 게이트를 우선하며, Redis queue 분리는 후속 hardening으로 둡니다.

## 2. RLS는 CI에서 실제 PostgreSQL로 검증

SQLite에서는 RLS가 no-op입니다. PostgreSQL service를 띄운 GitHub Actions에서 migration 후 비-superuser app role로 tenant isolation을 검증합니다.

## 3. SolverDiagnosticEvent는 최소 원인 저장부터

전체 assumption literal 진단 모델은 후속 범위입니다. 이번 단계에서는 solver가 만든 ScheduleIssue와 완화안 후보를 DB에 `infeasibility_core`, `unary_exclusion`, `manual_review` 이벤트로 저장해 “조치 가능한 진단 기록” 기준을 충족합니다.
