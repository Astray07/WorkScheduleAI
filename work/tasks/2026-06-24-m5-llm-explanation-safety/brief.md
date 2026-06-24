# M5 LLM Explanation Safety Brief

## 목표

LLM 설명 레이어를 독립 모듈로 분리하고, 개인정보 비전송과 fallback 동작을 테스트로 고정합니다.

## 비목표

- 실제 외부 LLM API를 호출하지 않습니다.
- 설명 품질 고도화나 eval dataset 대량 구축은 하지 않습니다.
- LLM이 solver 결과나 완화안 후보를 생성하게 만들지 않습니다.

## 성공 기준

- 익명화 payload에 직원 실명, 조직명, 이메일, 사번, note, 업로드 원문 문구가 포함되지 않습니다.
- LLM payload에 `estimated_loss_score` 같은 numeric loss score가 포함되지 않습니다.
- 요청 단위 pseudonym으로 후보자와 관계 충돌을 표현합니다.
- LLM 응답이 schema를 위반하거나 proposal type/reason code를 왜곡하면 fallback을 사용합니다.
- 기존 ScheduleRun API의 fallback 응답 계약이 유지됩니다.

## 제약

- fallback이 테스트와 로컬 개발의 기본 경로입니다.
- OpenAI API key는 필요하지 않습니다.
- 변경은 `llm` 모듈과 ScheduleRun fallback wiring에 한정합니다.
