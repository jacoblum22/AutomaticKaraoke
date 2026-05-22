# Automatic Karaoke

Turn an uploaded song into a karaoke MP4 with synced lyrics: vocal separation (Demucs), transcription and alignment (faster-whisper + WhisperX), and video burn-in (FFmpeg).

**Current phase:** Phase 5 next (FFmpeg + ASS render) — Phase 4 Whisper ✓, Phase 3 Demucs ✓, Phase 2 API on [Vercel](https://automatic-karaoke.vercel.app). Runbooks: [0](docs/PHASE_0.md) · [1](docs/PHASE_1.md) · [2](docs/PHASE_2.md) · [3](docs/PHASE_3.md) · [4](docs/PHASE_4.md).

**Repository:** https://github.com/jacoblum22/AutomaticKaraoke

**Live preview:** https://automatic-karaoke.vercel.app

**Full roadmap:** [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) · Phase runbooks: [0](docs/PHASE_0.md) · [1](docs/PHASE_1.md) · [2](docs/PHASE_2.md) · [3](docs/PHASE_3.md) · [4](docs/PHASE_4.md)

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
npm run smoke:modal         # client → deployed Modal API
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

Live: https://automatic-karaoke.vercel.app — footer should show **Mock mode: off**.

## Modal API (Phase 2)

```powershell
cd backend
modal deploy app.py
# API: https://jacoblum22--karaoke-api.modal.run
```

Smoke tests (repo root): `scripts/smoke_modal_deployed.py`, `scripts/smoke_job_durability.py`

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

## Project phases

| Phase | Focus |
|-------|--------|
| 0 | Repo skeleton, Vite scaffold, stubs |
| 1 | Frontend + mock job API ✓ |
| 2 | Modal job endpoints |
| 3 | Demucs isolation ✓ |
| 4 | Whisper + WhisperX ✓ |
| 5 | FFmpeg + ASS render (isolated) |
| 6 | Full pipeline integration |
| 7 | Hardening (upload, auth, performance) |

## License

TBD
