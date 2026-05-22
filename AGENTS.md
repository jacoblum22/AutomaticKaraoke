# Agent context — Automatic Karaoke

## Stack

- **Frontend:** Vite + React + TypeScript on Vercel (`frontend/`)
- **Backend:** Modal Python app with GPU (`backend/`)
- **Pipeline:** Demucs → faster-whisper on **vocal stem** → WhisperX align → FFmpeg + ASS → R2 URL

## Phase boundaries

- Build and test each layer in isolation before integrating (see `docs/IMPLEMENTATION_PLAN.md`).
- Phase 0: scaffold only — no upload UI, no Modal web endpoints, no ML installs.

## API contract (async)

1. `POST /start-job` → `{ job_id }` immediately
2. `GET /job-status?job_id=` polled every ~2s
3. On `status: "done"`, return `video_url`

Job statuses: `queued` | `separating` | `transcribing` | `aligning` | `rendering` | `done` | `failed`

Types live in `frontend/src/types/job.ts`.

## Critical pipeline rules

- Run transcription on **Demucs vocal stem**, not the full mix.
- Order: **Demucs first**, then transcribe+align, then render on instrumental.
- Do not parallelize Whisper with Demucs on the original file.

## Modal development

When editing `backend/`, prefer [Modal docs for LLMs](https://modal.com/docs/guide/developing-with-llms) and `https://modal.com/llms-full.txt`.

## What not to add in early phases

- No torch/demucs/whisper in Phase 0–2
- No Next.js / Turborepo patterns — this is Vite + Modal only
- Vercel plugins/MCP help hosting only, not GPU workers
