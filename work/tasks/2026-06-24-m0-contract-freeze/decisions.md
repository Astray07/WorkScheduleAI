# Decisions

## 1. M0 산출물 형식

OpenAPI 초안은 YAML이 아니라 JSON으로 작성합니다. 현재 저장소에 앱 스택과 의존성이 없으므로, Python 표준 라이브러리만으로 최소 파싱 검증을 할 수 있게 하기 위함입니다.

## 2. 스택 고정 수준

기획서의 권장 스택인 `React 또는 Next.js`, FastAPI, PostgreSQL, Redis, SQLAlchemy/Alembic, OR-Tools를 유지합니다. M0에서는 실제 프론트엔드 프레임워크를 `React`와 `Next.js` 중 하나로 확정하지 않고, HTTP 계약과 JSON fixture만 고정합니다.

## 3. ScheduleRun과 SchedulePublication 분리

M0 계약에서 ScheduleRun은 실행 기록, SchedulePublication은 발행된 확정본으로 분리합니다. 결과 API는 publication이 없을 때 `publication: null`, 발행 후에는 `read_only: true`와 publication payload를 반환합니다.

## 4. 미배정 표현

필요 역할 미충족은 assignment row를 만들지 않고 `ScheduleIssue.type = unfilled_requirement`로 표현합니다. M0 fixture도 이 방식을 따릅니다.

## 5. 재계산 카운터

`current_attempt_no`는 worker 기술 재시도 또는 attempt 구분용입니다. `recalculation_count`는 관리자 승인/수동 변경에 따른 재계산 라운드이며, 1차 릴리즈에서 최대 3회입니다.

## 6. LLM 계약

OpenAPI에는 LLM 호출 API를 M0 공개 계약으로 추가하지 않습니다. 대신 response의 `llm_explanation`은 서버 fallback 또는 비동기 설명 결과를 담는 표시 레이어로 정의합니다. 완화안의 원본 판단 근거는 서버가 만든 구조화 데이터입니다.

## 7. DB migration 계획 위치

실제 migration 파일은 애플리케이션 스캐폴딩 이후 생성합니다. M0에서는 테이블 생성 순서, 핵심 constraint, RLS, overlap 처리 방식을 `docs/contracts/m0-db-migration-plan.md`에 고정합니다.

