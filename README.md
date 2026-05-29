# Automatic Karaoke

Turn an uploaded song into a karaoke MP4 with synced lyrics: vocal separation (Demucs), transcription and alignment (faster-whisper + WhisperX), and video burn-in (FFmpeg).

**Current phase:** Phase 8 complete ✓ — polished upload → stepper progress → video card UX (Tailwind v4 + shadcn/ui). Pipeline unchanged on [Modal](https://jacoblum22--karaoke-api.modal.run), live app on [Vercel](https://automatic-karaoke.vercel.app). Runbooks: [0](docs/PHASE_0.md)–[7](docs/PHASE_7.md) · **[8 — UX](docs/PHASE_8.md)**.

**Repository:** https://github.com/jacoblum22/AutomaticKaraoke

**Live preview:** https://automatic-karaoke.vercel.app

**Full roadmap:** [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) · Phase runbooks: [0](docs/PHASE_0.md)–[7](docs/PHASE_7.md) · [8](docs/PHASE_8.md)

**UI (Phase 8):** Dark theme, drag-and-drop upload with file chip, pipeline stepper + progress bar, inline video player with download, collapsible **Debug** footer in local dev only.

**Storage (Phase 2+):** Plan to use Cloudflare R2 for finished MP4s; create an R2 bucket when wiring Modal secrets — not required for Phase 0.

## Prerequisites

- Node.js 20+ and npm
- Python 3.11 or 3.12
- [Modal](https://modal.com/) CLI (Phase 0 Step 4+): `pip install modal` then `modal token new`

## Quick start (frontend)

```bash
cd frontend
npm install
cp .env.modal .env.local    # Phase 2+: Modal API + VITE_API_KEY (or cp .env.example for mock)
npm run dev
```

Restart `npm run dev` after editing `.env.local`. Upload an audio file — real pipeline on **Modal** (`VITE_USE_MOCK=false`) or in-browser mock (`VITE_USE_MOCK=true`).

```bash
npm run build
npm run smoke:mock     # mock only
npm run smoke:modal         # client.ts → Modal API → real R2 video_url (~10–25 min)
npm run measure:start-job   # timing vs upload size (Modal)
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
| `VITE_API_KEY` | Same as Modal secret `karaoke-api-key` → `API_KEY` (when auth enabled) |

Live: https://automatic-karaoke.vercel.app — production footer: *GPU processing on Modal · Hosted on Vercel*. Local dev: expand **Debug** for mock/API/key status (never shows the raw key).

Redeploy Vercel after changing `VITE_*` (values are baked in at build time). Do not mark `VITE_API_KEY` as **Sensitive** on Vercel.

## Modal API (Phase 2+)

```powershell
cd backend
modal deploy app.py
# API: https://jacoblum22--karaoke-api.modal.run
```

Requires Modal secrets **`karaoke-r2`** (R2) and **`karaoke-api-key`** (optional `API_KEY`).

**Warm-up cost (intent-based):** selecting a file calls `POST /warm` (~$0.06–0.08 per bounce if the user never submits; GPUs idle out after 2 min). See [PHASE_7.md](docs/PHASE_7.md#cost-notes-intent-based-warm-up).

Smoke tests (repo root):

```powershell
.\.venv\Scripts\python.exe scripts\smoke_phase8_step7.py            # Phase 8 sign-off (steps 1–6 + verify)
.\.venv\Scripts\python.exe scripts\smoke_phase7_step8.py --verify-only
.\.venv\Scripts\python.exe scripts\smoke_pipeline_modal.py          # full E2E (~10–25 min)
```

Phase 8 gates: `scripts/smoke_phase8_step1.py` … `scripts/smoke_phase8_step7.py` — see [PHASE_8.md](docs/PHASE_8.md). Phase 7: [PHASE_7.md](docs/PHASE_7.md).

**Operational limits (production):**

| Policy | Value |
|--------|--------|
| Max upload size | 50 MB |
| Max song length | 8 minutes |
| Job retention | 24 hours (R2 + Volume + Dict; cron every 6h) |
| Rate limit | **5 job starts per hour per IP** (`start-job`, `finalize-job`) |
| Input upload | **Presigned PUT to R2** when R2 is configured (`GET /config` → `r2_upload`); fallback multipart to Modal |
| API key | Optional Modal secret **`karaoke-api-key`** (`API_KEY`); frontend `VITE_API_KEY` + `X-API-Key` header |

**R2 CORS (presigned upload):** apply [docs/r2-cors.example.json](docs/r2-cors.example.json) on your bucket (Cloudflare dashboard → R2 → bucket → Settings → CORS).

## Demucs (Phase 3) ✓

Install Demucs deps (separate from lean API `requirements.txt`):

```powershell
pip install -r backend/requirements-demucs.txt
.\.venv\Scripts\python.exe scripts\test_demucs_local.py
.\.venv\Scripts\python.exe scripts\save_vocal_fixture.py
```

Modal GPU separation:

```powershell
cd backend
..\.venv\Scripts\modal.exe run app.py::smoke_demucs_separate
..\.venv\Scripts\modal.exe deploy app.py
cd ..
.\.venv\Scripts\python.exe scripts\smoke_demucs_modal.py
```

Full-song quality (add your own MP3, gitignored): `scripts/copy_psychosomatic_fixture.py` → `scripts/smoke_phase3_step7.py`. Outputs: `scripts/output/psychosomatic/vocals.wav` + `instrumental.wav`. See [PHASE_3.md](docs/PHASE_3.md).

## Whisper (Phase 4) ✓

```powershell
pip install -r backend/requirements-whisper.txt
.\.venv\Scripts\python.exe scripts\test_whisper_local.py --clip-end 30
.\.venv\Scripts\python.exe scripts\validate_lyrics_json.py scripts\output\lyrics.json
.\.venv\Scripts\python.exe scripts\smoke_whisper_modal.py --deploy
.\.venv\Scripts\python.exe scripts\smoke_phase4_step5.py   # full-song lyrics.json
```

Requires `scripts/output/psychosomatic/vocals.wav` at deploy time (baked into `_WHISPER_IMAGE`). See [PHASE_4.md](docs/PHASE_4.md).

## Render (Phase 5) ✓

FFmpeg must be on PATH locally (`ffmpeg -version`). No extra pip deps for render (see `backend/requirements-render.txt`).

```powershell
.\.venv\Scripts\python.exe scripts\smoke_phase5_step1.py
.\.venv\Scripts\python.exe scripts\smoke_phase5_step3.py          # 30s clip
.\.venv\Scripts\python.exe scripts\smoke_phase5_step5.py          # full song → psychosomatic/karaoke.mp4
.\.venv\Scripts\python.exe scripts\smoke_render_modal.py --deploy # Modal CPU + API regression
```

Manual render:

```powershell
.\.venv\Scripts\python.exe scripts\test_render_local.py `
  --instrumental scripts\output\psychosomatic\instrumental.wav `
  --lyrics scripts\output\psychosomatic\lyrics.json `
  --output scripts\output\psychosomatic\karaoke.mp4 --no-clip
```

Bakes psychosomatic stems into Modal images at deploy. See [PHASE_5.md](docs/PHASE_5.md).

## Pipeline integration (Phase 6) ✓

Runbook: [PHASE_6.md](docs/PHASE_6.md) — Demucs → Whisper (`large-v3`, VAD off) → render → R2 `video_url`.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_pipeline_modal.py
.\.venv\Scripts\python.exe scripts\smoke_phase6_step8.py --verify-only
cd frontend && npm run smoke:modal
```

Prerequisites: R2 bucket + Modal secret `karaoke-r2`; Vercel `VITE_USE_MOCK=false`, `VITE_API_URL` = Modal base.

## Project phases

| Phase | Focus |
|-------|--------|
| 0 | Repo skeleton, Vite scaffold, stubs |
| 1 | Frontend + mock job API ✓ |
| 2 | Modal job endpoints |
| 3 | Demucs isolation ✓ |
| 4 | Whisper + WhisperX ✓ |
| 5 | FFmpeg + ASS render (isolated) ✓ |
| 6 | Full pipeline integration ✓ |
| 7 | Production hardening ✓ (see [PHASE_7.md](docs/PHASE_7.md)) |
| 8 | Frontend polish & UX ✓ (see [PHASE_8.md](docs/PHASE_8.md)) |

## License

TBD
