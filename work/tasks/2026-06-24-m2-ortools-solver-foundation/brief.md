# M2 OR-Tools Solver Foundation Brief

## 목표

1차 릴리즈 solver core의 기반으로 독립 OR-Tools CP-SAT solver 모듈을 추가합니다.

## 비목표

- ScheduleRun API에 solver를 연결하지 않습니다.
- DB에 Assignment/ScheduleIssue 저장 테이블을 추가하지 않습니다.
- 완화안 승인 후 재계산 로직을 solver에 연결하지 않습니다.
- 대형 100명/31일 성능 최적화는 하지 않습니다.

## 성공 기준

- 4명/1주/2역할 golden case가 모든 요구사항을 배정합니다.
- 휴가/불가 일정, 역할 자격, blocked pair가 hard constraint로 적용됩니다.
- 채울 수 없는 필요 인원은 실패가 아니라 `unfilled_requirement` issue가 됩니다.
- 동일 입력은 동일 assignment 순서를 반환합니다.
- 전체 테스트가 통과합니다.

## 제약

- OR-Tools가 근무표 생성 책임을 갖습니다.
- LLM은 사용하지 않습니다.
- solver DTO는 SQLAlchemy/FastAPI와 분리합니다.
