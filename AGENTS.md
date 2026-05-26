# Agent context — Automatic Karaoke

## Stack

- **Frontend:** Vite + React + TypeScript on Vercel (`frontend/`)
- **Backend:** Modal Python app with GPU (`backend/`)
- **Pipeline:** Demucs → faster-whisper on **vocal stem** → WhisperX align → FFmpeg + ASS → R2 URL

## Phase boundaries

- Build and test each layer in isolation before integrating (see `docs/IMPLEMENTATION_PLAN.md`).
- Phase 0: scaffold only — no upload UI, no Modal web endpoints, no ML installs.

## API contract (async)

Production UI flow (Phase 7):

1. `POST /warm` on file select (optional, `warmIfNeeded()` client-side)
2. `POST /draft-job` → `{ job_id }`
3. Upload: presigned R2 (`POST /upload-url` → PUT → `POST /draft-job/{id}/sync-upload`) or legacy `POST /draft-job/{id}/upload`
4. `POST /finalize-job?job_id=` → spawns pipeline (rate-limited; requires `X-API-Key` when `API_KEY` set)
5. `GET /job-status?job_id=` polled every ~2s
6. On `status: "done"`, `video_url` points at R2 `karaoke/{job_id}/karaoke.mp4`

Legacy: `POST /start-job` (multipart one-shot) for smokes.

`GET /config` → `{ r2_upload, api_key_required }` (public).

Job statuses: `queued` | `separating` | `transcribing` | `aligning` | `rendering` | `done` | `failed`

Types live in `frontend/src/types/job.ts`.

## Critical pipeline rules

- Run transcription on **Demucs vocal stem**, not the full mix.
- Order: **Demucs first**, then transcribe+align, then render on instrumental.
- Do not parallelize Whisper with Demucs on the original file.

## Modal development

When editing `backend/`, prefer [Modal docs for LLMs](https://modal.com/docs/guide/developing-with-llms) and `https://modal.com/llms-full.txt`.

### Secrets (`modal.Secret`)

- **`karaoke-r2`:** `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_ENDPOINT_URL`, `R2_PUBLIC_BASE_URL`
- **`karaoke-api-key`:** `API_KEY` (optional; when set, protected routes need `X-API-Key`)

### Vercel env (production)

- `VITE_USE_MOCK=false`, `VITE_API_URL` = Modal base
- `VITE_API_KEY` = same value as Modal `API_KEY` when auth enabled (baked at build; not Sensitive on Vercel)

## What not to add in early phases

- No torch/demucs/whisper in Phase 0–2
- No Next.js / Turborepo patterns — this is Vite + Modal only
- Vercel plugins/MCP help hosting only, not GPU workers
