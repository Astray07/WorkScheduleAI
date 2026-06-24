# M4 Frontend P0 UI Brief

## 목표

브라우저에서 P0 흐름을 시연할 수 있는 운영형 React UI를 추가합니다.

## 비목표

- 마케팅 랜딩 페이지를 만들지 않습니다.
- 인증/회원가입 UI를 완성하지 않습니다.
- 고급 정책 UI, 드래그 앤 드롭, 생성 이력 비교는 구현하지 않습니다.
- 정식 Excel 업로드 UI는 구현하지 않습니다.

## 성공 기준

- 첫 화면에서 P0 demo setup과 결과 검토 흐름을 볼 수 있습니다.
- API로 조직, 직원, 휴가, 상극 조합, ScheduleRun을 생성합니다.
- 완화안 승인, 재계산, 확정, Excel 다운로드 액션을 실행할 수 있습니다.
- schedule grid, ScheduleIssue, RelaxationProposal, published read-only 상태가 표시됩니다.
- `npm run build`, backend tests, browser verification이 통과합니다.

## 제약

- 운영형 도구 UI로 구현합니다.
- 텍스트와 버튼이 모바일/데스크톱에서 겹치지 않아야 합니다.
- OpenAI API key는 사용하지 않습니다.
