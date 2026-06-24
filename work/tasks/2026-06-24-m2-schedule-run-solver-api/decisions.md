# M2 ScheduleRun Solver API Decisions

## 1. shift template 존재 시 solver path 사용

기존 테스트와 mock UI 계약을 깨지 않기 위해 shift template이 없는 조직은 기존 mock path를 유지합니다. 1차 릴리즈 UI는 shift template을 생성한 뒤 solver-backed ScheduleRun을 사용하도록 연결합니다.

## 2. 승인 후 재계산 고도화는 분리

이번 작업은 ScheduleRun result 생성 경로를 OR-Tools에 연결하는 데 집중합니다. 승인된 완화안이 unavailability 또는 pair constraint를 완화하는 solver input 변환은 후속 작업으로 분리합니다.

## 3. ScheduleIssue는 response DTO로 매핑

아직 ScheduleIssue 영속 테이블은 없으므로 solver issue를 기존 result response의 `ScheduleIssueResponse`로 매핑합니다.
