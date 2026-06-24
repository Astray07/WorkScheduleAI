# M0 Contract Overview

## 목적

이 문서는 WorkScheduleAI M0 계약 고정 산출물의 안내서입니다. M0는 실제 앱 구현을 시작하기 전에 API, worker, DB, frontend가 공유할 계약을 고정하는 단계입니다.

## 현재 저장소 상태

- 애플리케이션 코드는 아직 없습니다.
- Git 저장소가 아직 초기화되어 있지 않습니다.
- 루트 `AGENTS.md` 파일은 없습니다. 현재 대화에 제공된 AGENTS 지침을 적용합니다.
- 권장 스택은 기획서 기준으로 FastAPI, PostgreSQL, Redis, SQLAlchemy/Alembic, OR-Tools, React 또는 Next.js입니다.

## M0 고정 범위

- OpenAPI 초안: `docs/contracts/openapi.m0.json`
- ScheduleRun 상태 머신: `docs/contracts/schedule-run-state-machine.md`
- DB migration 계획: `docs/contracts/m0-db-migration-plan.md`
- mock UI fixtures: `docs/contracts/fixtures/*.json`

## P0 Vertical Slice 계약 추적

| 흐름 | M0 계약 위치 |
| --- | --- |
| 조직 생성 | `POST /organizations` |
| 직원 4명 bulk paste | `POST /organizations/{organization_id}/employees/bulk-paste` |
| 휴가 1건 | `POST /organizations/{organization_id}/unavailabilities` |
| 상극 조합 1건 | `POST /organizations/{organization_id}/pair-constraints` |
| 1주 근무표 생성 | `POST /organizations/{organization_id}/schedule-runs` |
| 상태 polling | `GET /organizations/{organization_id}/schedule-runs/{schedule_run_id}` |
| 결과 그리드 | `GET /organizations/{organization_id}/schedule-runs/{schedule_run_id}/result` |
| 완화안 승인 | `POST /organizations/{organization_id}/schedule-runs/{schedule_run_id}/relaxation-proposals/{proposal_id}/approve` |
| 재계산 | `POST /organizations/{organization_id}/schedule-runs/{schedule_run_id}/recalculate` |
| 확정 | `POST /organizations/{organization_id}/schedule-runs/{schedule_run_id}/publications` |
| 엑셀 다운로드 | `GET /organizations/{organization_id}/schedule-publications/{publication_id}/excel` |

## Mock UI Acceptance

- `p0-schedule-run-running.json`으로 상태 polling UI를 만들 수 있어야 합니다.
- `p0-result-before-relaxation.json`으로 1주 결과 그리드, 미배정 이슈, 단일 완화안 카드를 만들 수 있어야 합니다.
- `p0-result-after-recalculation.json`으로 승인된 override 표시, 경고 상태, 미배정 해소 상태를 만들 수 있어야 합니다.
- 내부 점수 숫자는 일반 UI에 직접 노출하지 않고 severity label로 표시합니다.
- 묶음 완화안은 M0 schema에 표현 가능하지만 1차 UI에서는 읽기 전용 또는 수동 조정 폴백으로 처리합니다.

## 개인정보와 LLM

근무표 생성과 완화안 생성은 OR-Tools 및 서버 로직이 담당합니다. LLM은 서버가 만든 구조화 결과를 설명하는 레이어이며, 직원 실명, 조직명, 휴가 상세 사유를 포함한 개인정보를 전달하지 않습니다. LLM 실패나 schema 위반 시 서버 fallback 문구를 사용합니다.

