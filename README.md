# Automatic Karaoke

Turn an uploaded song into a karaoke MP4 with synced lyrics: vocal separation (Demucs), transcription and alignment (faster-whisper + WhisperX), and video burn-in (FFmpeg).

**Current phase:** Phase 0 — project scaffold (see [docs/PHASE_0.md](docs/PHASE_0.md)).

**Full roadmap:** [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)

## Prerequisites

- Node.js 20+ and npm
- Python 3.11 or 3.12
- [Modal](https://modal.com/) CLI (Phase 0 Step 4+): `pip install modal` then `modal token new`

## Quick start (frontend)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — you should see the Phase 0 placeholder page.

```bash
npm run build
```

## Python / Modal (after Step 4)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
modal profile
```

## Project phases

| Phase | Focus |
|-------|--------|
| 0 | Repo skeleton, Vite scaffold, stubs |
| 1 | Frontend + mock job API |
| 2 | Modal job endpoints |
| 3–5 | Demucs, Whisper+WhisperX, FFmpeg (isolated scripts) |
| 6 | Full pipeline integration |
| 7 | Hardening (upload, auth, performance) |

## License

TBD
