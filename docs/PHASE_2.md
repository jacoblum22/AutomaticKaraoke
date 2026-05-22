# Phase 2 — Backend Shell (Modal, No ML)

**Parent doc:** [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)  
**Prerequisite:** [PHASE_1.md](./PHASE_1.md) complete (Steps 1–8)  
**Estimated time:** 6–12 hours  
**Goal:** Real HTTP endpoints and durable job lifecycle on Modal — pipeline steps are **stubs** (sleep + status updates) that return a known test video URL. **No** Demucs, Whisper, FFmpeg, or R2 uploads yet.

**Out of scope for Phase 2:** GPU functions, `separate.py` / `transcribe.py` / `render.py` logic, presigned R2 uploads, auth, rate limits, production MP4 generation from real audio.

### Current progress

| Status | Steps |
|--------|--------|
| Not started | **1–8** — job store → endpoints → deploy → frontend wiring → Vercel |

**Frontend (Phase 1, still mock on Vercel):** https://automatic-karaoke.vercel.app — `VITE_USE_MOCK=true` until Step 7.

**Modal workspace:** `jacoblum22` (CLI authenticated in Phase 0).

**Next after Phase 2:** [Phase 3 — Demucs in isolation](./IMPLEMENTATION_PLAN.md#phase-3--demucs-in-isolation).

---

## Entry criteria

Before starting Phase 2:

- [ ] [Phase 1 exit](./PHASE_1.md#exit-criteria--phase-2) satisfied (completion checklist + local/Vercel mock flow)
- [ ] `cd frontend && npm run build` passes on `main`
- [ ] `modal profile current` shows `jacoblum22`
- [ ] Vercel project **`automatic-karaoke`** only (no second CLI project)
- [ ] `frontend/src/types/job.ts` unchanged — backend responses must match these types
- [ ] Phase 1 UI works with `VITE_USE_MOCK=true` (baseline to compare against)

---

## Architecture (Phase 2)

```text
Browser (Vercel or npm run dev, VITE_USE_MOCK=false)
       ↓  POST multipart /start-job  (field: audio)
Modal web_endpoint → create job in modal.Dict → spawn orchestrator stub
       ↓
Orchestrator stub (background): sleep ~2s per stage, update Dict
  queued → separating → transcribing → aligning → rendering → done
       ↓
GET /job-status?job_id= → read Dict
       ↓
status === "done" → video_url (stable HTTPS test MP4)
```

**Job store (required):** `modal.Dict.from_name("karaoke-jobs", create_if_missing=True)` — survives container restarts; not in-memory-only on a single worker.

**Stub orchestrator:** No GPU. Each stage updates `status`, `progress`, `message` in the Dict. On `done`, set `video_url` to a **stable public test MP4** (see [video URL choice](#video_url-for-phase-2-stub)).

**Audio upload in Phase 2:** Accept the file in `POST /start-job` (validate size/type server-side if easy), optionally write to a Modal Volume path for debugging — **do not** require R2. The stub pipeline does not read the audio bytes.

| Approach | Phase 2 | Phase 6+ |
|----------|---------|----------|
| Job state | `modal.Dict` | Same + Volume artifacts per job |
| Video delivery | Public HTTPS test URL | R2 signed URL |
| CORS | Allow Vercel production + preview origins | Same |
| Frontend mock | Off when testing real API | Off in production |

---

## Target repository tree (Phase 2 changes)

Primary work in **`backend/`**. Small **`frontend/`** env and copy updates only.

```text
backend/
├── .env.example                 (update) — document Dict name, optional R2 placeholders
├── requirements.txt             (unchanged) — modal only; no torch/demucs yet
├── app.py                       (content) — Modal App, web endpoints, CORS, spawn stub
├── jobs.py                      (content) — Dict CRUD, JobRecord shape, helpers
├── orchestrator.py              (content) — stub pipeline (sleep + status updates)
├── storage.py                   (stub) — R2 helpers deferred to Phase 6/7
├── separate.py                  (stub) — unchanged
├── transcribe.py                (stub) — unchanged
└── render.py                    (stub) — unchanged

frontend/
├── .env.example                 (update) — VITE_USE_MOCK=false path, VITE_API_URL
├── .env.local                   (gitignored) — your Modal web base for local dev
└── src/
    ├── api/client.ts            (verify) — fetch paths already stubbed; test with mock off
    └── App.tsx                  (optional) — subtitle “Phase 2 — Modal stub API”

scripts/
└── smoke_modal_api.py           (content) — curl-equivalent: start job + poll until done

docs/
└── PHASE_2.md                     (this file)
```

**Not created in Phase 2:**

| Path | Phase |
|------|-------|
| `separate.py` GPU function | 3 |
| `transcribe.py` | 4 |
| `render.py` FFmpeg | 5 |
| R2 bucket + secrets | 6/7 |
| `scripts/fixtures/sample_30s.mp3` | 3 |

---

## API contract (must match Phase 1 / `job.ts`)

Same shapes as [PHASE_1 API contract](./PHASE_1.md#api-contract-same-as-phase-2). Frontend `client.ts` already implements these when mock is off.

### `POST /start-job`

- **Request:** `multipart/form-data`, field name **`audio`** (matches `client.ts` `FormData.append("audio", file)`).
- **Response:** `200` + `{ "job_id": "<uuid>" }` within **&lt;2 seconds** (spawn orchestrator asynchronously; do not wait for pipeline).
- **Errors:** `400` invalid file; `413` too large; `500` internal.

### `GET /job-status?job_id=<uuid>`

- **Response:** `JobStatusResponse` JSON.
- **404** if unknown `job_id`.

```typescript
// frontend/src/types/job.ts — do not change without updating backend
status: "queued" | "separating" | "transcribing" | "aligning" | "rendering" | "done" | "failed"
```

### Stub timing (suggested)

| Stage | Delay (stub) | `status` | `progress` |
|-------|----------------|----------|------------|
| Start | 0s | `queued` | 0 |
| 1 | ~2s | `separating` | 20 |
| 2 | ~2s | `transcribing` | 40 |
| 3 | ~2s | `aligning` | 60 |
| 4 | ~2s | `rendering` | 80 |
| Done | — | `done` | 100 + `video_url` |

Total ~8–10s — close enough to Phase 1 mock for UI testing.

### `video_url` for Phase 2 stub

Pick **one** stable HTTPS URL and use it for every successful job:

| Option | URL | Notes |
|--------|-----|-------|
| **A (recommended)** | `https://automatic-karaoke.vercel.app/sample.mp4` | Already deployed; CORS-friendly for `<video src>` |
| B | Same origin as Phase 1 mock: `/sample.mp4` | Only works if API and player share origin — **not** when API is on Modal |
| C | R2 public object | Requires bucket setup — defer unless you already have R2 |

Document the chosen URL in `orchestrator.py` as a constant.

### CORS

On both web endpoints, allow:

- `https://automatic-karaoke.vercel.app`
- `https://*.vercel.app` (preview deploys)
- `http://localhost:5173` and `http://localhost:5174` (Vite dev)

Return appropriate headers for `OPTIONS` preflight.

---

## File minimums

### `backend/jobs.py`

- `JOBS = modal.Dict.from_name("karaoke-jobs", create_if_missing=True)`
- Typed dict or dataclass for: `job_id`, `status`, `progress`, `message`, `video_url`, `error`, `created_at` (ISO string)
- `create_job(job_id: str) -> None` — initial `queued`
- `get_job(job_id: str) -> dict | None`
- `update_job(job_id: str, **fields) -> None`
- `set_failed(job_id: str, error: str) -> None`

### `backend/orchestrator.py`

- `@app.function()` (CPU, no GPU) `run_stub_pipeline(job_id: str) -> None`
- Loop stages with `time.sleep(2)` (or `modal.sleep` if preferred)
- Call `jobs.update_job` after each stage
- On success: `status="done"`, `progress=100`, `video_url=STUB_VIDEO_URL`
- Wrap in `try/except` → `set_failed` on unexpected errors

### `backend/app.py`

- `app = modal.App("karaoke")` (keep name)
- Import `orchestrator`, `jobs`
- `@modal.web_endpoint(method="POST")` → `start_job`: parse upload, `job_id = uuid4()`, `create_job`, `run_stub_pipeline.spawn(job_id)`, return `{job_id}`
- `@modal.web_endpoint(method="GET")` → `job_status`: read query `job_id`, return JSON or 404
- CORS helper or `modal.web_endpoint` CORS kwargs per Modal docs
- Deploy: `modal deploy app.py` from `backend/`

### `backend/.env.example`

```env
# Phase 2 — optional local notes (secrets go in Modal dashboard, not committed)
# MODAL_APP_NAME=karaoke
# STUB_VIDEO_URL=https://automatic-karaoke.vercel.app/sample.mp4

# Phase 6+ — R2 (Modal Secret)
# R2_ACCESS_KEY_ID=
# R2_SECRET_ACCESS_KEY=
# R2_BUCKET=
# R2_ENDPOINT_URL=
```

### `frontend/.env.example` (update)

```env
# Phase 2+: real Modal API
VITE_USE_MOCK=false
VITE_API_URL=https://<your-workspace>--karaoke-api.modal.run

# Phase 1 only: set VITE_USE_MOCK=true and ignore VITE_API_URL
```

### `frontend/.env.local` (for Phase 2 dev)

```env
VITE_USE_MOCK=false
VITE_API_URL=https://<your-workspace>--karaoke-api.modal.run
```

After `modal deploy`, copy the web endpoint base URL from CLI output (no trailing slash).

### `scripts/smoke_modal_api.py`

- Uses `httpx` or `requests` (add to dev deps or stdlib `urllib`)
- POST a small file from `scripts/fixtures/` or generate minimal bytes
- Poll `job-status` every 2s until `done` or `failed`
- Print stages; exit 0 on `done` with `video_url`

---

## Step-by-step execution order

Complete in order. Each **Gate** must pass before the next step.

### Step 1 — Job store (`jobs.py`)

| # | Action |
|---|--------|
| 1.1 | Implement `jobs.py` with `modal.Dict` |
| 1.2 | Optional: `modal run` one-off script to create/read/update/delete a test job |

**Gate:**

- [ ] `create_job` + `get_job` + `update_job` work from a Modal function or local `modal run`
- [ ] Dict entry persists after the test function exits (re-read in a second invocation)

**First testable point:** isolated job store — no HTTP yet.

---

### Step 2 — Stub orchestrator

| # | Action |
|---|--------|
| 2.1 | Add `orchestrator.py` with `run_stub_pipeline(job_id)` |
| 2.2 | `modal run orchestrator.py::run_stub_pipeline --job-id <test-uuid>` (or spawn from a scratch function) |

**Gate:**

- [ ] Dict shows full progression `queued` → … → `done` with `video_url` set
- [ ] Simulated failure path sets `failed` + `error` (optional `raise` test)

**Second testable point:** background pipeline without web endpoints.

---

### Step 3 — Web endpoints + CORS

| # | Action |
|---|--------|
| 3.1 | Implement `POST /start-job` and `GET /job-status` in `app.py` |
| 3.2 | Wire `start-job` → `create_job` + `run_stub_pipeline.spawn` |
| 3.3 | Add CORS for Vercel + localhost |

**Gate:**

- [ ] `modal serve app.py` (dev): `curl`/script POST returns `job_id` in &lt;2s
- [ ] Poll until `done`; `video_url` present
- [ ] Preflight `OPTIONS` from browser origin succeeds (check Network tab later)

**Third testable point:** HTTP API via `modal serve` + `scripts/smoke_modal_api.py`.

---

### Step 4 — Deploy to Modal

| # | Action |
|---|--------|
| 4.1 | `cd backend && modal deploy app.py` |
| 4.2 | Record deployed web base URL in `frontend/.env.local` and notes |
| 4.3 | Run `smoke_modal_api.py` against **deployed** URL (not just serve) |

**Gate:**

- [ ] Deploy succeeds; URL is HTTPS and stable across redeploys (same workspace app name)
- [ ] Smoke script passes against production Modal URL
- [ ] `modal app list` shows `karaoke` app

---

### Step 5 — Frontend local against Modal

| # | Action |
|---|--------|
| 5.1 | Set `VITE_USE_MOCK=false` and `VITE_API_URL=<modal base>` in `.env.local` |
| 5.2 | Restart `npm run dev`; footer shows **Mock mode: off** |
| 5.3 | Full upload → poll → video (test MP4 URL) |

**Gate:**

- [ ] No CORS errors in browser console
- [ ] Progress stages match stub timing
- [ ] `<video>` plays the stub `video_url` (cross-origin MP4 OK)

**Fourth testable point:** end-to-end in local dev with real Modal API.

---

### Step 6 — Job durability check

| # | Action |
|---|--------|
| 6.1 | Start a job; while running, redeploy or wait for cold start on another poll |
| 6.2 | Confirm `job-status` still returns correct state from Dict (not lost) |

**Gate:**

- [ ] Job survives at least one container recycle / redeploy during polling
- [ ] Unknown `job_id` returns 404, not 500

---

### Step 7 — Vercel + real API

| # | Action |
|---|--------|
| 7.1 | Vercel → **automatic-karaoke** → Environment Variables |
| 7.2 | Set `VITE_USE_MOCK` = `false` for **Production** (and Preview if used) |
| 7.3 | Set `VITE_API_URL` = Modal web base (no trailing slash) |
| 7.4 | Push to `main`; wait for deploy |
| 7.5 | Test upload flow on https://automatic-karaoke.vercel.app |

**Gate:**

- [ ] Production UI uses Modal (footer **Mock mode: off**)
- [ ] Full happy path on production URL
- [ ] No failed fetch to `localhost` in console

**Do not** create a second Vercel project from `frontend/` CLI ([Phase 0 lesson](./PHASE_0.md#lessons-learned-phase-0-retrospective)).

---

### Step 8 — Docs + README

| # | Action |
|---|--------|
| 8.1 | Update root `README.md` — Phase 2 in progress/complete, Modal deploy commands |
| 8.2 | Link `PHASE_2.md` from [IMPLEMENTATION_PLAN](./IMPLEMENTATION_PLAN.md) repo layout |
| 8.3 | Check off [completion checklist](#phase-2-completion-checklist) |
| 8.4 | Commit + push to `main` |

**Gate:**

- [ ] GitHub `main` has Phase 2 backend + doc updates
- [ ] Vercel production deploy uses real API env vars

---

## Phase 2 completion checklist

**All required boxes** must be checked before [Phase 3](./IMPLEMENTATION_PLAN.md#phase-3--demucs-in-isolation).

### Backend — job store + API

- [ ] `jobs.py` uses `modal.Dict` named `karaoke-jobs`
- [ ] `orchestrator.py` stub advances all `JobStatus` values including `aligning`
- [ ] `app.py` exposes `POST /start-job` and `GET /job-status`
- [ ] `start-job` returns in &lt;2s; work runs in spawned function
- [ ] CORS allows `automatic-karaoke.vercel.app`, preview `*.vercel.app`, localhost dev ports
- [ ] `modal deploy app.py` succeeds from `backend/`

### Frontend integration

- [ ] `VITE_USE_MOCK=false` documented in `.env.example`
- [ ] `client.ts` works against deployed Modal base URL
- [ ] Local `npm run dev` — full happy path with mock **off**
- [ ] https://automatic-karaoke.vercel.app — full happy path with mock **off**

### Verification scripts

- [ ] `scripts/smoke_modal_api.py` passes against deployed URL
- [ ] Job state readable after container recycle (Step 6)

### Explicitly NOT done (confirm)

- [ ] No Demucs / torch in `requirements.txt` or images
- [ ] No faster-whisper / WhisperX
- [ ] No FFmpeg render
- [ ] No R2 upload of user audio or output MP4 (stub URL only)
- [ ] No presigned upload flow

---

## Exit criteria → Phase 3

Phase 2 is **complete** when:

1. [Completion checklist](#phase-2-completion-checklist) required items are checked.
2. Browser → Modal `start-job` → poll → play **test** `video_url` works on **local** and **Vercel** without mock.
3. Job state lives in `modal.Dict`, not only in a single container’s RAM.
4. `separate.py` remains a stub; [Phase 3](./IMPLEMENTATION_PLAN.md#phase-3--demucs-in-isolation) adds Demucs in isolation.

**Next:** [Phase 3 — Demucs in isolation](./IMPLEMENTATION_PLAN.md#phase-3--demucs-in-isolation) — `scripts/test_demucs_local.py` + Modal GPU function; outputs `vocals.wav` + `instrumental.wav`.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| CORS blocked on Vercel | Add production origin to Modal endpoint; redeploy |
| CORS blocked on localhost | Allow `http://localhost:5173` / `5174` |
| `start-job` hangs &gt;2s | Spawn orchestrator; return `job_id` immediately |
| `job-status` always `queued` | Check spawn ran; inspect Modal logs for `run_stub_pipeline` |
| `video_url` 404 in player | Use full HTTPS URL (Vercel `sample.mp4`), not `/sample.mp4` on Modal host |
| `VITE_*` unchanged on Vercel | Redeploy after env change; rebuild required |
| Dict “empty” after deploy | Dict is workspace-scoped; use consistent app name `karaoke` |
| 404 on `job_id` | Client polling wrong id or job expired / wrong Dict name |
| PowerShell `&&` fails | Use `;` between commands |
| Two Vercel projects | Keep **`automatic-karaoke`** only |

---

## Modal commands reference

```powershell
# From repo root — activate venv first
cd backend
modal profile current
modal serve app.py          # local dev: hot-reload web endpoints
modal deploy app.py         # production URL for Vercel + smoke script
modal app logs karaoke      # tail orchestrator / endpoint logs
```

Copy the **web endpoint base URL** from deploy output into `VITE_API_URL`. Paths in `client.ts`:

- `${API_BASE}/start-job`
- `${API_BASE}/job-status?job_id=...`

Ensure `API_BASE` has no trailing slash.

---

## Lessons learned (Phase 2 retrospective)

*Fill this table when Phase 2 is done — same format as [PHASE_0](./PHASE_0.md#lessons-learned-phase-0-retrospective).*

| Topic | Planned | What happened | Doc / process fix |
|-------|---------|---------------|-------------------|
| | | | |

---

*Phase 2 planning doc v1.0 — runbook for Modal shell; ML isolation starts Phase 3.*
