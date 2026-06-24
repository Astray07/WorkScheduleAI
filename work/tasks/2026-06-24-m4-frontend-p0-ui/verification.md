# M4 Frontend P0 UI Verification

## 의존성 설치

명령:

```powershell
cd frontend
npm install
npm install -D @types/react @types/react-dom playwright
```

결과:

- 설치 성공
- npm audit: low severity 1건 보고됨. 기능/빌드 차단은 아니며 후속 dependency hardening에서 처리합니다.

## 빌드

명령:

```powershell
cd frontend
npm run build
```

결과:

- TypeScript build 통과
- Vite production build 통과

## 백엔드 스모크

명령:

```powershell
python -m pytest tests\api\test_api_smoke.py -q
```

결과:

- `2 passed`

## 브라우저 검증

준비:

```powershell
python -m alembic upgrade head
python -m uvicorn work_schedule_ai.api.app:create_app --factory --host 127.0.0.1 --port 8000
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

결과:

- `GET /health` -> `{"status":"ok"}`
- Vite `http://127.0.0.1:5173` -> 200
- Playwright로 P0 흐름 실행:
  - 조직 생성
  - 직원 4명 생성
  - 휴가 1건 생성
  - 상극 조합 1건 생성
  - 1주 ScheduleRun 생성
  - 완화안 승인
  - 재계산
  - 확정
  - Excel 다운로드
- 스케줄 row: 7개
- 재계산 후 열린 ScheduleIssue 없음
- 확정 후 `읽기 전용` 상태 표시
- Excel 다운로드 파일: `C:\Users\c\AppData\Local\Temp\workscheduleai-p0-schedule.xlsx`
- 데스크톱 스크린샷: `C:\Users\c\AppData\Local\Temp\workscheduleai-p0-desktop.png`
- 모바일 스크린샷: `C:\Users\c\AppData\Local\Temp\workscheduleai-p0-mobile.png`
- 최종 Playwright run: console error 없음, failed request 없음
- 레이아웃 폭 확인:
  - desktop `scrollWidth=1440`, `clientWidth=1440`
  - mobile `scrollWidth=390`, `clientWidth=390`

## 전체 검증

명령:

```powershell
python -m pytest -q
git diff --check
```

결과:

- `89 passed in 4.06s`
- `git diff --check` exit 0
- 줄바꿈 경고: 일부 파일이 다음 Git touch 시 CRLF로 바뀔 수 있다는 경고만 표시됨

## 커밋

- `feat: add p0 frontend workflow`
