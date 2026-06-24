# Decisions

## 2026-06-24

- 이번 단계에서는 SchedulePublication을 만들지 않습니다. ScheduleRun은 실행 기록이고 확정본은 별도 테이블/흐름이라는 제품 원칙을 유지합니다.
- result table 전체를 먼저 만들지 않고, deterministic mock result를 API 레이어에서 생성합니다. OR-Tools 통합 전 UI 계약 고정이 목적이기 때문입니다.
- `status=succeeded`, `solver_status=not_started`를 사용합니다. mock 결과가 준비되었지만 실제 solver는 실행하지 않았음을 명확히 하기 위해서입니다.
- 생성 기간은 inclusive day count로 1-31일을 검증합니다.
- `Idempotency-Key`는 같은 조직 안에서 unique하게 저장합니다. 같은 키로 재호출하면 기존 ScheduleRun을 반환합니다.
- LLM 설명은 `status=fallback`, `source=server_template`만 반환합니다. 외부 LLM 호출이나 개인정보 전송은 없습니다.
