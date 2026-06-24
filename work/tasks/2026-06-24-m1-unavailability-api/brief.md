# Brief

## 목표

P0 vertical slice의 휴가 1건 등록 단계를 위해 `POST /organizations/{organization_id}/unavailabilities` API를 구현합니다.

## 비목표

- 불가 일정 bulk paste
- 겹침/중복 일정 정책
- 일반 사용자 휴가 신청
- solver 반영
- LLM 설명 생성

## 성공 기준

- 단건 불가 일정을 201로 생성합니다.
- `type`은 `vacation`, `business_trip`, `training`, `personal`만 허용합니다.
- `ends_at`은 `starts_at`보다 뒤여야 합니다.
- 요청 조직에 속한 직원만 참조할 수 있습니다.
- Alembic head migration이 `unavailabilities` 테이블과 조회 인덱스를 생성합니다.
- 기존 전체 테스트가 계속 통과합니다.

## 제약과 가정

- `note`는 저장만 하며 LLM 전송 경로와 연결하지 않습니다.
- 조직/직원 권한 검사는 인증 도입 전까지 API 입력 검증으로만 처리합니다.
- 날짜/시간은 OpenAPI 초안의 `date-time` 형식을 우선합니다.
