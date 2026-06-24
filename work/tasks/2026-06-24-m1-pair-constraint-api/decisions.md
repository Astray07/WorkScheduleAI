# Decisions

## 2026-06-24

- 새 DB 모델이나 migration은 추가하지 않습니다. `PairConstraint` 모델, normalized unique constraint, domain 테스트가 이미 존재합니다.
- `severity` 누락 시 `high`로 저장합니다. P0의 상극 조합은 조직 리스크가 큰 제약이며 제품 계획의 penalty 표에서도 높은 손실로 봅니다.
- API에서 역순 중복을 사전에 조회해 409로 반환합니다. DB unique constraint만 의존하면 사용자에게 충돌 의미를 명확히 주기 어렵습니다.
- `none` severity는 이번 P0 pair constraint API에서 받지 않습니다. 기존 DB constraint와 P0 상극 조합 흐름을 우선 맞춥니다.
