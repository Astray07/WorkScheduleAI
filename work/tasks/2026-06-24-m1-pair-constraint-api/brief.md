# Brief

## 목표

P0 vertical slice의 상극 조합 1건 등록 단계를 위해 `POST /organizations/{organization_id}/pair-constraints` API를 구현합니다.

## 비목표

- pair constraint bulk paste
- 고급 제약 편집 UI
- solver 반영
- 완화안 승인/재계산

## 성공 기준

- 단건 pair constraint를 201로 생성합니다.
- employee 순서와 무관하게 normalized pair를 저장하고 응답합니다.
- 자기 자신 조합은 422로 거부합니다.
- 다른 조직 직원 참조는 422로 거부합니다.
- 역순 중복은 409로 거부합니다.
- 기존 전체 테스트가 계속 통과합니다.

## 제약과 가정

- M0 OpenAPI에서 `severity`는 선택 값이며, 이번 API는 누락 시 `high`를 기본값으로 저장합니다.
- 기존 DB check constraint가 허용하는 severity 값은 `low`, `medium`, `high`, `critical`입니다. `none` severity는 이번 P0 상극 조합 입력 범위에서 제외합니다.
