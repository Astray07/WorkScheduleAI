# M5 LLM Explanation Safety Decisions

## 1. Whitelist payload builder

익명화는 민감 필드를 제거하는 blacklist가 아니라 LLM에 보낼 필드만 새로 구성하는 whitelist 방식으로 구현합니다.

## 2. Pseudonym은 요청 단위

직원 id, 사번, 이메일, 실명은 payload에 보내지 않고, payload 생성 중 메모리에만 존재하는 `P1`, `P2` alias로 치환합니다.

## 3. fallback 기본값 유지

외부 LLM provider 호출은 1차 릴리즈에서 선택 사항입니다. 테스트와 로컬 개발에서는 provider 응답이 없거나 잘못된 경우 항상 서버 템플릿 fallback을 사용합니다.
