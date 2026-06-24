# M1 P0 Vertical Slice API Test Brief

## 목표

P0 흐름인 조직 생성부터 Excel 다운로드까지의 API 연결을 하나의 통합 테스트로 고정합니다.

## 비목표

- 새 product 기능을 추가하지 않습니다.
- 프론트엔드 UI를 만들지 않습니다.
- OR-Tools 실제 solver 또는 LLM 호출을 연결하지 않습니다.

## 성공 기준

- in-memory DB 기반 TestClient가 P0 순서대로 endpoint를 호출합니다.
- 재계산 후 issue가 해소되고 publication이 생성됩니다.
- publication Excel 다운로드 응답이 실제 `.xlsx` zip workbook입니다.
- 전체 테스트가 통과합니다.

## 제약

- 테스트는 public API만 사용합니다.
- PII를 LLM이나 외부 서비스로 보내지 않습니다.
- Excel 업로드는 v1 범위이므로 테스트하지 않습니다.
