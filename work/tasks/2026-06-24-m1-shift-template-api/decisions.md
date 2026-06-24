# M1 Shift Template API Decisions

## 1. ShiftType과 ShiftRequirement를 함께 생성

1차 UI에서 근무 유형과 필요 인원을 따로 저장하는 복잡한 편집 흐름보다, 한 요청에서 같이 생성하는 단순한 API를 우선합니다.

## 2. 반복 규칙은 아직 저장하지 않음

제품 기획의 반복 규칙은 1차에서 제한된 프리셋만 필요합니다. 이번 모델에는 start/end/timezone/crosses_midnight와 active만 넣고, RRULE 전체 편집은 후속으로 둡니다.

## 3. ShiftSlot 저장은 solver 증분으로 분리

이번 작업은 master data 계약입니다. 실제 날짜별 슬롯 생성과 snapshot 포함은 OR-Tools solver 증분에서 다룹니다.
