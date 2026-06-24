# First Release Execution Decisions

## 1. 한 번에 전체 제품을 만들지 않음

1차 릴리즈까지 진행하되, 각 단계는 독립 테스트와 커밋이 가능한 작은 증분으로 나눕니다.

## 2. 다음 증분은 ShiftType/ShiftRequirement

현재 P0 API는 기본 역할과 mock 결과를 다루지만, 1차 릴리즈 성공 기준의 “근무 유형/커스텀 역할별 필요 인원”이 없습니다. Solver 입력 계약을 안정화하기 위해 shift template 모델과 API를 먼저 구현합니다.

## 3. OR-Tools 설치는 solver 증분에서 검증

현재 로컬 환경에는 OR-Tools가 설치되어 있지 않습니다. solver 증분에서 `pyproject.toml` 의존성 추가와 실제 import 검증을 수행합니다.

## 4. UI는 운영형 첫 화면

프론트엔드는 마케팅 랜딩 페이지를 만들지 않고, 조직 설정부터 결과 검토까지 이어지는 운영형 화면을 첫 화면으로 구성합니다.
