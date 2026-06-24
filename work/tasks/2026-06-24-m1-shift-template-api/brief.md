# M1 Shift Template API Brief

## 목표

1차 릴리즈의 근무 유형/필요 인원 설정을 위해 `ShiftType`과 `ShiftRequirement` 모델 및 API를 추가합니다.

## 비목표

- 반복 규칙 전체 편집기를 구현하지 않습니다.
- ShiftSlot 저장 테이블을 만들지 않습니다.
- solver 연결은 이번 작업에서 하지 않습니다.
- 근무 유형 UI는 이번 작업에서 만들지 않습니다.

## 성공 기준

- 조직별 shift type 이름 중복이 막힙니다.
- shift type 생성 시 역할별 필요 인원을 함께 저장합니다.
- 존재하지 않거나 다른 조직의 role은 거절합니다.
- migration head가 shift template 테이블을 만듭니다.
- 전체 테스트가 통과합니다.

## 제약

- 변경 범위는 backend model/API/test/migration으로 제한합니다.
- 1차에서는 제한된 하루 단위 템플릿 입력만 지원합니다.
