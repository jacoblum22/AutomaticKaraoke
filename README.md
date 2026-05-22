# Automatic Karaoke

Turn an uploaded song into a karaoke MP4 with synced lyrics: vocal separation (Demucs), transcription and alignment (faster-whisper + WhisperX), and video burn-in (FFmpeg).

**Current phase:** Phase 1 complete → starting [Phase 2](docs/IMPLEMENTATION_PLAN.md#phase-2--backend-shell-only-modal-no-ml) (Modal API shell). Runbooks: [PHASE_1.md](docs/PHASE_1.md), [PHASE_0.md](docs/PHASE_0.md).

**Repository:** https://github.com/jacoblum22/AutomaticKaraoke

**Live preview:** https://automatic-karaoke.vercel.app

**Full roadmap:** [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) · Phase runbooks: [0](docs/PHASE_0.md) · [1](docs/PHASE_1.md) · [2](docs/PHASE_2.md)

**Storage (Phase 2+):** Plan to use Cloudflare R2 for finished MP4s; create an R2 bucket when wiring Modal secrets — not required for Phase 0.

## Prerequisites

- Node.js 20+ and npm
- Python 3.11 or 3.12
- [Modal](https://modal.com/) CLI (Phase 0 Step 4+): `pip install modal` then `modal token new`

## Quick start (frontend)

```bash
cd frontend
npm install
cp .env.example .env.local   # VITE_USE_MOCK=true for Phase 1
npm run dev
```

Open http://localhost:5173 — upload an audio file to run the **mock** job (no GPU, no Modal). Progress advances through separation → transcription → alignment → render; on completion, a sample video plays.

```bash
npm run build
npm run smoke:mock    # mock API only
npm run smoke:client  # client.ts via mock (needs .env.local)
```

## Python / Modal (Step 4)

From the repo root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
python -c "import modal"
modal token new    # one-time browser login
modal profile current
```

Use **two terminals** for day-to-day dev: one with `cd frontend && npm run dev`, one with the venv activated for `modal` / `python scripts/...`.

Optional editor setup: `.vscode/extensions.json`, project context in `AGENTS.md` — see [docs/PHASE_0.md](docs/PHASE_0.md#cursor-and-editor-tooling-optional).

## Vercel (production preview)

Project: **automatic-karaoke** (root `frontend/`), linked to GitHub `main`.

Required env for Phase 1 mock on Vercel:

- `VITE_USE_MOCK` = `true` (Production + Preview)
- `VITE_API_URL` — optional while mock is on; ignored when `VITE_USE_MOCK=true`

Live: https://automatic-karaoke.vercel.app

## Project phases

| Phase | Focus |
|-------|--------|
| 0 | Repo skeleton, Vite scaffold, stubs |
| 1 | Frontend + mock job API ✓ |
| 2 | Modal job endpoints |
| 3–5 | Demucs, Whisper+WhisperX, FFmpeg (isolated scripts) |
| 6 | Full pipeline integration |
| 7 | Hardening (upload, auth, performance) |

## License

TBD
