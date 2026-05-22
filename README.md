# Automatic Karaoke

Turn an uploaded song into a karaoke MP4 with synced lyrics: vocal separation (Demucs), transcription and alignment (faster-whisper + WhisperX), and video burn-in (FFmpeg).

**Current phase:** Phase 2 — Modal stub API on [Vercel](https://automatic-karaoke.vercel.app) + local dev. Runbooks: [PHASE_2.md](docs/PHASE_2.md), [PHASE_1.md](docs/PHASE_1.md), [PHASE_0.md](docs/PHASE_0.md).

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
cp .env.modal .env.local    # Phase 2: real Modal API (or cp .env.example for mock)
npm run dev
```

Upload an audio file — stub pipeline hits **Modal** (`VITE_USE_MOCK=false`) or in-browser mock (`VITE_USE_MOCK=true`).

```bash
npm run build
npm run smoke:mock     # mock only
npm run smoke:modal    # client → deployed Modal API
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

## Vercel (production)

Project: **automatic-karaoke** (root `frontend/`), linked to GitHub `main`.

**Phase 2 production env:**

| Variable | Value |
|----------|--------|
| `VITE_USE_MOCK` | `false` |
| `VITE_API_URL` | `https://jacoblum22--karaoke-api.modal.run` |

Live: https://automatic-karaoke.vercel.app — footer should show **Mock mode: off**.

## Modal API (Phase 2)

```powershell
cd backend
modal deploy app.py
# API: https://jacoblum22--karaoke-api.modal.run
```

Smoke tests (repo root): `scripts/smoke_modal_deployed.py`, `scripts/smoke_job_durability.py`

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
