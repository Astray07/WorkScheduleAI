# M4 Frontend P0 UI Decisions

## 1. Vite React 사용

저장소에 기존 프론트엔드 스택이 없고 새 복합 app UI이므로 Vite React를 사용합니다.

## 2. 첫 화면은 운영 화면

프론트엔드는 랜딩 페이지가 아니라 실제 P0 운영 워크플로우를 첫 화면으로 보여줍니다.

## 3. API demo flow 우선

초기 UI는 데모 데이터 생성을 자동화해 조직 생성부터 다운로드까지 한 화면에서 시연 가능하게 합니다. 인증은 후속 release hardening으로 둡니다.

## 4. Playwright dev dependency 추가

브라우저 플러그인의 직접 조작 도구가 노출되지 않아 Playwright를 dev dependency로 추가했습니다. 1차 릴리즈 UI 검증은 실제 브라우저 클릭 흐름과 스크린샷으로 확인합니다.

## 5. favicon 추가

Vite 앱의 브라우저 콘솔에서 favicon 404가 발생해 작은 SVG favicon을 추가했습니다. 기능 범위 확장은 아니며 브라우저 검증 노이즈 제거 목적입니다.
