# M1 P0 Vertical Slice API Test Decisions

## 1. 테스트 전용 증분

이미 개별 endpoint는 구현되어 있으므로 이번 단계는 production code를 건드리지 않고 public API 호출 순서를 고정합니다.

## 2. 실제 DB fixture 대신 생성 API 사용

조직, 직원, 휴가, 상극 조합은 DB seed가 아니라 실제 API로 생성합니다. 이렇게 해야 데모 흐름에서 깨지는 계약을 더 빨리 잡을 수 있습니다.

## 3. Excel은 zip 구조로 검증

워크북을 파일로 저장하지 않고 응답 bytes를 `zipfile`로 열어 `.xlsx` 패키지 구조와 핵심 sheet 내용을 확인합니다.
