# M1 Publication Excel API Decisions

## 1. publication을 Excel보다 먼저 구현

M0 OpenAPI의 다운로드 경로는 `GET /organizations/{organization_id}/schedule-publications/{publication_id}/excel`입니다. 따라서 run에서 바로 다운로드하는 임시 API를 만들지 않고, 최소 `SchedulePublication`을 먼저 생성합니다.

## 2. mock result 기반 snapshot hash

아직 solver assignment 저장 테이블이 없으므로 publication은 현재 mock result의 assignments/issues를 정렬 JSON으로 hash하여 stale publish를 방지합니다. 실제 Assignment/ScheduleIssue 저장소가 생기면 같은 필드명을 유지하고 hash 계산 입력만 교체합니다.

## 3. 표준 라이브러리 xlsx 생성

엑셀 포맷이 아직 MVP 최소형이므로 `openpyxl` 의존성을 추가하지 않습니다. Python 표준 라이브러리로 최소 `.xlsx` zip 패키지를 생성하고, 고급 서식은 후속 export hardening으로 남깁니다.

## 4. 겹치는 active publication 방지

기획서 기준에 따라 같은 조직에서 `published` 상태의 publication 기간이 일부라도 겹치면 409로 막습니다. archive/split 흐름은 후속 범위입니다.
