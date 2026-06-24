# M4 Frontend P0 UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Vite React frontend that demonstrates the P0 operations workflow from setup through Excel download.

**Architecture:** Create a `frontend/` app that calls the FastAPI backend via `VITE_API_BASE_URL`. The first screen is the actual operational workflow: setup rail, schedule grid, issue/proposal panel, and release actions. No marketing landing page is included.

**Tech Stack:** Vite, React, TypeScript, CSS, lucide-react, FastAPI CORS for local dev.

---

### Task 1: Frontend Scaffold and UI

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/styles.css`
- Modify: `.gitignore`

- [x] **Step 1: Add React app files**

Build the operational UI with setup workflow, schedule grid, issue/proposal panel, approve/recalculate/publish/download controls, API status, and error feedback.

- [x] **Step 2: Install dependencies**

Run:

```powershell
cd frontend
npm install
```

Expected: dependencies install successfully.

### Task 2: Backend Dev CORS

**Files:**
- Modify: `src/work_schedule_ai/api/app.py`

- [x] **Step 1: Add local CORS middleware**

Allow `http://localhost:5173` and `http://127.0.0.1:5173` for Vite dev.

- [x] **Step 2: Run backend tests**

Run:

```powershell
python -m pytest tests/api/test_api_smoke.py -q
```

Expected: pass.

### Task 3: Build and Browser Verification

**Files:**
- Modify: `work/tasks/2026-06-24-m4-frontend-p0-ui/verification.md`

- [x] **Step 1: Run build**

Run:

```powershell
cd frontend
npm run build
```

Expected: TypeScript and Vite build pass.

- [x] **Step 2: Run backend and frontend dev servers**

Run FastAPI on `127.0.0.1:8000` and Vite on `127.0.0.1:5173`.

- [x] **Step 3: Verify rendered UI**

Use Browser plugin if available; otherwise use Playwright fallback. Verify app loads, no framework overlay, console health, desktop screenshot, mobile screenshot, and P0 interaction path.

### Task 4: Full Verification and Commit

**Files:**
- Modify: `work/tasks/2026-06-24-m4-frontend-p0-ui/verification.md`
- Modify: `work/tasks/2026-06-24-m4-frontend-p0-ui/handoff.md`

- [x] **Step 1: Run full verification**

Run:

```powershell
python -m pytest -q
git diff --check
```

Expected: all tests pass and whitespace check exits 0.

- [x] **Step 2: Commit**

Run:

```powershell
git add .gitignore frontend src/work_schedule_ai/api/app.py docs/superpowers/plans/2026-06-24-m4-frontend-p0-ui.md work/tasks/2026-06-24-m4-frontend-p0-ui
git commit -m "feat: add p0 frontend workflow"
```
