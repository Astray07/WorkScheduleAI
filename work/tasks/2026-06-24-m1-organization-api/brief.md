# Brief

## 목표

M1 도메인 API의 첫 vertical endpoint로 `POST /organizations`를 구현합니다. 조직 생성 시 기본 역할 `사수`, `부사수`를 함께 저장하고 M0 OpenAPI의 OrganizationResponse 형태로 반환합니다.

## 비목표

- 인증과 현재 사용자 식별은 구현하지 않습니다.
- 사용자 1명당 조직 1개 제한은 아직 구현하지 않습니다.
- membership 자동 생성은 인증 이후로 둡니다.
- 조직 switcher나 다중 조직 UX는 구현하지 않습니다.

## 성공 기준

- `POST /organizations`가 201을 반환합니다.
- response에 조직 id, name, timezone, data_version, 기본 역할 2개가 포함됩니다.
- DB에 organization row와 role row 2개가 저장됩니다.
- 빈 조직명은 422로 거부됩니다.
- 테스트를 먼저 작성하고 RED 실패를 확인한 뒤 GREEN 통과합니다.

## 제약

- TDD 순서를 지킵니다.
- route는 DB session dependency를 통해 동작해야 합니다.
- 기본 역할명은 기획서 기준 `사수`, `부사수`입니다.

