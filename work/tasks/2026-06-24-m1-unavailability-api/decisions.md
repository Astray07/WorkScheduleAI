# Decisions

## 2026-06-24

- `Unavailability`는 기존 0001 migration을 수정하지 않고 새 Alembic revision으로 추가합니다. 이미 커밋된 foundation migration의 의미를 보존하기 위해서입니다.
- 조직 소속 employee 검증은 이번 API 레이어에서 수행합니다. 기존 employees 테이블에는 `(organization_id, id)` 복합 unique가 없어 DB 복합 FK를 지금 추가하면 영향 범위가 커집니다.
- `note`는 DB에 저장하지만 LLM 설명 경로와 연결하지 않습니다. 개인정보/자유 텍스트는 익명화 계층 전까지 외부로 보내지 않는다는 제품 원칙을 유지합니다.
- 겹치는 휴가/불가 일정 정책은 아직 기획상 P0 필수 흐름이 아니므로 이번 단건 생성 API에서는 검사하지 않습니다.
