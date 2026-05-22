# Phase 2 — Backend Shell (Modal, No ML)

**Parent doc:** [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)  
**Prerequisite:** [PHASE_1.md](./PHASE_1.md) complete (Steps 1–8)  
**Estimated time:** 6–12 hours  
**Goal:** Real HTTP endpoints and durable job lifecycle on Modal — pipeline steps are **stubs** (sleep + status updates) that return a known test video URL. **No** Demucs, Whisper, FFmpeg, or R2 uploads yet.

**Out of scope for Phase 2:** GPU functions, `separate.py` / `transcribe.py` / `render.py` logic, presigned R2 uploads, auth, rate limits, production MP4 generation from real audio.

### Current progress

**Phase 2 status: complete** (May 2026). All eight steps done; see [completion checklist](#phase-2-completion-checklist) and [what differed from the plan](#what-differed-from-the-plan).

| Status | Steps |
|--------|--------|
| Done | **1** `jobs.py` + `modal.Dict` |
| Done | **2** `orchestrator.py` stub pipeline |
| Done | **3** HTTP + CORS (`karaoke-api` via FastAPI ASGI) |
| Done | **4** `modal deploy` + production smoke |
| Done | **5** frontend `.env.modal` + `npm run smoke:modal` |
| Done | **6** job durability + 404 |
| Done | **7** Vercel production env (`VITE_USE_MOCK=false`) |
| Done | **8** README + docs + `main` |

**Production:** https://automatic-karaoke.vercel.app — `VITE_USE_MOCK=false`, `VITE_API_URL=https://jacoblum22--karaoke-api.modal.run`.

**Modal API:** https://jacoblum22--karaoke-api.modal.run (`modal deploy` from `backend/`, label `karaoke-api`).

**Next:** [Phase 3 — Demucs in isolation](./PHASE_3.md).

---

## Entry criteria

Before starting Phase 2 (all satisfied):

- [x] [Phase 1 exit](./PHASE_1.md#exit-criteria--phase-2) satisfied
- [x] `cd frontend && npm run build` passes on `main`
- [x] `modal profile current` shows `jacoblum22`
- [x] Vercel project **`automatic-karaoke`** only
- [x] `frontend/src/types/job.ts` unchanged
- [x] Phase 1 UI worked with `VITE_USE_MOCK=true` (baseline)

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

**Audio upload in Phase 2:** Accept the file in `POST /start-job` (validate size/type server-side), drain the multipart body in 1 MB chunks (stub does not use bytes). No R2, no Volume write.

**Client UX (post-Phase 2):** Progress UI appears **immediately** on button click (“Uploading and starting job…”). The browser still blocks on `start-job` until the **full file is uploaded** and the server responds — large MP3s can take several seconds before real pipeline stages appear. Dev console: `[timing] start-job` / `first job-status`. Benchmark: `cd frontend && npm run measure:start-job`.

| Approach | Phase 2 | Phase 6+ |
|----------|---------|----------|
| Job state | `modal.Dict` | Same + Volume artifacts per job |
| Video delivery | Public HTTPS test URL | R2 signed URL |
| CORS | Allow Vercel production + preview origins | Same |
| Frontend mock | Off when testing real API | Off in production |

---

## Target repository tree (as built)

```text
backend/
├── .env.example
├── requirements.txt             modal + fastapi[standard] (no ML deps)
├── app.py                       App "karaoke", _BACKEND_IMAGE, smoke fns, @asgi_app karaoke-api
├── web.py                       FastAPI create_api(): /start-job, /job-status, CORS
├── jobs.py                      modal.Dict "karaoke-jobs"
├── orchestrator.py              run_stub_pipeline (sleep stages, STUB_VIDEO_URL)
├── storage.py, separate.py, transcribe.py, render.py  (stubs)

frontend/
├── .env.example, .env.modal     committed template for Modal API
├── .env.local                   gitignored
├── package.json                 smoke:modal, measure:start-job
├── tsconfig.scripts.json        vite-node scripts (Node types)
├── scripts/
│   ├── smoke-client-modal.ts
│   └── measure-start-job-timing.ts
└── src/
    ├── api/client.ts
    ├── App.tsx                  optimistic progress + dev timing logs
    └── components/…             ProgressTracker indeterminate bar during upload

scripts/
├── smoke_jobs_dict.py
├── smoke_orchestrator.py
├── smoke_modal_api.py           --serve (Windows UTF-8 fix)
├── smoke_modal_deployed.py
└── smoke_job_durability.py      defaults to production URL
```

---

## What differed from the plan

| Topic | Planned | What we built |
|-------|---------|----------------|
| HTTP layer | `@modal.web_endpoint` on `app.py` | **FastAPI** in `web.py`, mounted with `@modal.asgi_app(label="karaoke-api")` |
| `requirements.txt` | modal only | `modal` + **`fastapi[standard]`** |
| Backend packaging | Implicit mount of entry file | **`_BACKEND_IMAGE`** + `add_local_dir(backend)` so `jobs.py` / `web.py` import in all containers |
| `start-job` latency | Response in **&lt;2s** (spawn only) | **Spawn is async**, but HTTP **waits for full multipart upload** + drain; cold start adds **3–8+ s** on first request (see `measure:start-job`) |
| Progress UI | Show after API returns | **Immediate** queued state + indeterminate bar on click; real stages after `start-job` + first poll |
| Smoke entry | Single `smoke_modal_api.py` | Plus **`smoke_modal_deployed.py`**, **`smoke_job_durability.py`**, **`smoke_jobs_dict.py`**, **`smoke_orchestrator.py`**, frontend **`smoke:modal`** |
| Step 1 gate | Optional `modal run` | Dedicated **`scripts/smoke_jobs_dict.py`** + `app.py` smoke functions |
| Dev URL | Documented `-dev` suffix | **`smoke_job_durability`** defaults to **production** URL; unset `MODAL_API_URL` if `-dev` endpoint stopped |
| Vercel env | Dashboard | CLI `vercel env add … --force` + **`main` push** (Git-linked deploy) |
| Upload body | `await audio.read()` once | **Spawn job first**, then **drain in 1 MB chunks** (stub ignores bytes) |

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
- **Response:** `200` + `{ "job_id": "<uuid>" }`. Orchestrator runs in a **spawned** function (pipeline not awaited). The HTTP handler still **waits for the client to finish uploading** the multipart body before responding — so wall-clock time scales with file size and Modal cold start (not a fixed &lt;2s from the browser).
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

### `backend/app.py` + `backend/web.py`

- `app = modal.App("karaoke")`
- `_BACKEND_IMAGE` — `debian_slim` + `pip_install_from_requirements` + **`add_local_dir(backend)`** (required for imports in containers)
- `run_stub_pipeline` `@app.function` wraps `orchestrator.run_stub_pipeline`
- `@modal.asgi_app(label="karaoke-api")` → `karaoke_api()` returns `web.create_api(spawn_pipeline=…)`
- Step 1 smoke: `smoke_jobs_write`, `smoke_jobs_read`, `smoke_jobs_failed`, `smoke_orchestrator_happy`, `smoke_orchestrator_fail`
- Deploy: `modal deploy app.py` from `backend/`

### `backend/web.py`

- FastAPI routes: `POST /start-job`, `GET /job-status`
- CORS: production Vercel origin, `allow_origin_regex` for `*.vercel.app`, localhost 5173/5174
- `start-job`: validate type/size → `create_job` → `spawn_pipeline` → drain upload in chunks → `{ job_id }`

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

- [x] `create_job` + `get_job` + `update_job` work from Modal (`app.py` smoke functions)
- [x] Dict entry persists after the test function exits (`smoke_jobs_read` in a new container)

**First testable point:** isolated job store — run from repo root:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_jobs_dict.py
```

Or: `cd backend` then `modal run app.py::smoke_jobs_write` (look for `JOB_ID=…` in output).

---

### Step 2 — Stub orchestrator

| # | Action |
|---|--------|
| 2.1 | Add `orchestrator.py` with `run_stub_pipeline(job_id)` |
| 2.2 | `modal run orchestrator.py::run_stub_pipeline --job-id <test-uuid>` (or spawn from a scratch function) |

**Gate:**

- [x] Dict shows full progression `queued` → … → `done` with `video_url` set
- [x] Simulated failure path sets `failed` + `error` (`simulate_fail` on transcribing)

**Second testable point:** background pipeline without web endpoints:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_orchestrator.py
```

Expect ~20–40s (2× `modal run`; stub pipeline ~8s of sleeps inside the happy poll).

---

### Step 3 — Web endpoints + CORS

| # | Action |
|---|--------|
| 3.1 | Implement `web.py` (FastAPI) + mount via `@modal.asgi_app` in `app.py` |
| 3.2 | Wire `start-job` → `create_job` + `run_stub_pipeline.spawn` |
| 3.3 | Add CORS for Vercel + localhost |

**Gate:**

- [x] `modal serve app.py` (dev): POST returns `job_id` quickly (~1s; spawn is async)
- [x] Poll until `done`; `video_url` present
- [x] Preflight `OPTIONS` from `http://localhost:5173` succeeds

**Third testable point:** HTTP API via `modal serve` + smoke script:

```powershell
# Auto-starts modal serve, runs test, then stops serve
.\.venv\Scripts\python.exe scripts\smoke_modal_api.py --serve

# Or: modal serve in one terminal, then:
$env:MODAL_API_URL="https://<workspace>--karaoke-api-dev.modal.run"
.\.venv\Scripts\python.exe scripts\smoke_modal_api.py
```

Dev URL label: **`karaoke-api`** → `https://jacoblum22--karaoke-api-dev.modal.run` (with `-dev` suffix while serving).

---

### Step 4 — Deploy to Modal

| # | Action |
|---|--------|
| 4.1 | `cd backend && modal deploy app.py` |
| 4.2 | Record deployed web base URL in `frontend/.env.local` and notes |
| 4.3 | Run `smoke_modal_api.py` against **deployed** URL (not just serve) |

**Gate:**

- [x] Deploy succeeds; URL is HTTPS and stable across redeploys (app `karaoke`, label `karaoke-api`)
- [x] Smoke script passes against production Modal URL
- [x] `modal app list` shows `karaoke` app

**Production API base:** https://jacoblum22--karaoke-api.modal.run

**Fourth testable point:**

```powershell
cd backend
modal deploy app.py
cd ..
.\.venv\Scripts\python.exe scripts\smoke_modal_deployed.py
```

---

### Step 5 — Frontend local against Modal

| # | Action |
|---|--------|
| 5.1 | Set `VITE_USE_MOCK=false` and `VITE_API_URL=<modal base>` in `.env.local` |
| 5.2 | Restart `npm run dev`; footer shows **Mock mode: off** |
| 5.3 | Full upload → poll → video (test MP4 URL) |

**Gate:**

- [x] `npm run smoke:modal` — client layer against deployed API (no browser CORS)
- [x] No CORS errors in browser (`npm run dev` + `.env.modal` → `.env.local`)
- [x] Progress stages match stub timing; **immediate** bar on click (upload phase)
- [x] `<video>` plays stub `video_url` (`https://automatic-karaoke.vercel.app/sample.mp4`)

**Fifth testable point:** end-to-end in local dev with real Modal API.

```powershell
# Option A — copy env and use dev server
copy frontend\.env.modal frontend\.env.local
cd frontend
npm run dev
# Footer: Mock mode: off, API URL shown. Upload a small MP3.

# Option B — automated client smoke (no browser)
cd frontend
npm run smoke:modal
```

---

### Step 6 — Job durability check

| # | Action |
|---|--------|
| 6.1 | Start a job; while running, redeploy or wait for cold start on another poll |
| 6.2 | Confirm `job-status` still returns correct state from Dict (not lost) |

**Gate:**

- [x] Job survives many polls across HTTP requests (Dict, not per-container RAM)
- [x] Optional: survives `modal deploy` mid-job (`--redeploy-mid`)
- [x] Unknown `job_id` returns 404, not 500

**Sixth testable point:**

```powershell
# Uses production URL by default (not MODAL_API_URL / -dev)
.\.venv\Scripts\python.exe scripts\smoke_job_durability.py
# Stronger (redeploy while job runs, ~1 min):
.\.venv\Scripts\python.exe scripts\smoke_job_durability.py --redeploy-mid
```

If you see `app for invoked web endpoint is stopped`, your shell still has `MODAL_API_URL` pointing at the **-dev** serve URL. Either run `modal serve` in `backend/`, or:

```powershell
Remove-Item Env:MODAL_API_URL -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe scripts\smoke_job_durability.py
```

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

- [x] Production env: `VITE_USE_MOCK=false`, `VITE_API_URL` = Modal web base
- [x] Production UI uses Modal (footer **Mock mode: off**)
- [x] Full happy path on production URL (upload → stub stages → sample MP4)
- [x] No failed fetch to `localhost` in console

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

- [x] GitHub `main` has Phase 2 backend + doc updates (`5dc4046`)
- [x] Vercel production deploy uses real API env vars + CLI/`main` deploy (May 2026)

---

## Phase 2 completion checklist

**All required boxes** must be checked before [Phase 3](./IMPLEMENTATION_PLAN.md#phase-3--demucs-in-isolation).

### Backend — job store + API

- [x] `jobs.py` uses `modal.Dict` named `karaoke-jobs`
- [x] `orchestrator.py` stub advances all `JobStatus` values including `aligning`
- [x] `app.py` exposes `POST /start-job` and `GET /job-status` (via `web.py` + `karaoke_api` ASGI)
- [x] `start-job` spawns pipeline without awaiting it; HTTP waits for upload drain (not &lt;2s for large files — see [deviations](#what-differed-from-the-plan))
- [x] CORS allows `automatic-karaoke.vercel.app`, preview `*.vercel.app`, localhost dev ports
- [x] `modal deploy app.py` succeeds from `backend/`

### Frontend integration

- [x] `VITE_USE_MOCK=false` documented in `.env.example` / `.env.modal`
- [x] `client.ts` works against deployed Modal base URL (`npm run smoke:modal`)
- [x] Local `npm run dev` — full happy path with mock **off**
- [x] https://automatic-karaoke.vercel.app — full happy path with mock **off**

### Verification scripts

- [x] `scripts/smoke_modal_api.py` / `smoke_modal_deployed.py` pass against deployed URL
- [x] Job state readable after many polls / optional mid-job redeploy (Step 6)
- [x] `npm run measure:start-job` — upload-size timing baseline

### Explicitly NOT done (confirmed)

- [x] No Demucs / torch in `requirements.txt` or images
- [x] No faster-whisper / WhisperX
- [x] No FFmpeg render
- [x] No R2 upload of user audio or output MP4 (stub URL only)
- [x] No presigned upload flow

---

## Exit criteria → Phase 3

Phase 2 is **complete** (May 2026):

1. [Completion checklist](#phase-2-completion-checklist) — all required items checked.
2. Browser → Modal `start-job` → poll → play **test** `video_url` on **local** and **Vercel** without mock.
3. Job state in `modal.Dict` (`karaoke-jobs`), not per-container RAM only.
4. `separate.py` still a stub — [Phase 3](./IMPLEMENTATION_PLAN.md#phase-3--demucs-in-isolation) adds Demucs in isolation.

**Known limitation (defer to Phase 6+):** `start-job` blocks on full file upload; no presigned R2 or upload progress % yet.

**Next:** [Phase 3 — Demucs in isolation](./PHASE_3.md) — `scripts/test_demucs_local.py` + Modal GPU function; outputs `vocals.wav` + `instrumental.wav`.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| CORS blocked on Vercel | Add production origin to Modal endpoint; redeploy |
| CORS blocked on localhost | Allow `http://localhost:5173` / `5174` |
| UI frozen after click, no bar | Fixed: optimistic `queued` + indeterminate bar; redeploy frontend if old build |
| `start-job` slow (3–8s+) | Normal: full MP3 upload + Modal cold start; run `npm run measure:start-job` |
| `start-job` hangs minutes | Check network tab; confirm `VITE_API_URL` is production Modal URL, not stopped `-dev` |
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

| Topic | Planned | What happened | Doc / process fix |
|-------|---------|---------------|-------------------|
| Modal imports | Mount `app.py` only | Only entry file mounted by default → `ImportError` for `jobs` | **`add_local_dir(backend)`** on shared image; document in Phase 2 tree |
| HTTP on Modal | `web_endpoint` decorators | FastAPI ASGI app cleaner for CORS + two routes | `web.py` + `@asgi_app`; add FastAPI to `requirements.txt` |
| `start-job` SLA | &lt;2s response | Client waits for **entire upload**; 5 MB ≈ 8s in testing | Don’t promise &lt;2s to browser; spawn async; Phase 6+ presigned upload |
| Progress UX | Bar after API | Users thought app was broken during upload | Optimistic UI + `measure:start-job`; note in architecture |
| Smoke / Windows | Print ✓ in subprocess | `charmap` encode error on `smoke_modal_api --serve` | UTF-8 stdio in script; avoid fancy chars in smoke output |
| Durability smoke | Use `MODAL_API_URL` | Stale **-dev** URL → “endpoint stopped” | Default production URL; document `Remove-Item Env:MODAL_API_URL` |
| Vercel | Dashboard env only | CLI `--force` + git push both needed | Step 7 lists CLI + `main` push |
| TS smoke scripts | `tsx` on `client.ts` | `process` not defined under default `tsc` | `tsconfig.scripts.json` + `vite-node` |

---

*Phase 2 runbook v2.0 — complete May 2026; Phase 3 adds Demucs.*
