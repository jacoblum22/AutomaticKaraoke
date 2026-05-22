# Automatic Karaoke

Turn an uploaded song into a karaoke MP4 with synced lyrics: vocal separation (Demucs), transcription and alignment (faster-whisper + WhisperX), and video burn-in (FFmpeg).

**Current phase:** Phase 0 complete → starting Phase 1 (see [docs/PHASE_0.md](docs/PHASE_0.md)).

**Repository:** https://github.com/jacoblum22/AutomaticKaraoke

**Live preview:** https://automatic-karaoke.vercel.app

**Full roadmap:** [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)

**Storage (Phase 2+):** Plan to use Cloudflare R2 for finished MP4s; create an R2 bucket when wiring Modal secrets — not required for Phase 0.

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

## Vercel preview (Step 7)

**Option A — Dashboard (after GitHub push):** [vercel.com/new](https://vercel.com/new) → Import `jacoblum22/AutomaticKaraoke` → Root Directory: `frontend` → Framework: Vite → add env `VITE_API_URL` = `http://localhost:5173` (placeholder).

**Option B — CLI:**

```powershell
cd frontend
npx vercel login
npx vercel --yes
npx vercel env add VITE_API_URL production   # paste placeholder URL when prompted
```

Preview should show the Phase 0 placeholder page (“Automatic Karaoke — scaffold ready”).

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
