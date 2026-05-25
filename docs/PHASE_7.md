# Phase 7 — Production Hardening

**Parent doc:** [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)  
**Prerequisite:** [PHASE_6.md](./PHASE_6.md) exit criteria (full pipeline, R2 `video_url`, E2E smokes, live site verified)  
**Estimated time:** 12–24 hours (incremental; each step is independently shippable)  
**Goal:** Make the deployed product **faster, safer, and cheaper to operate** without changing the core pipeline order (Demucs → transcribe+align → render → R2). Improve cold-start latency, add guardrails (duration, rate limits), lifecycle cleanup for storage, and observability for debugging production jobs.

**Out of scope for Phase 7:** Lyric accuracy overhaul (manual lyric editor, Genius API), payments/subscriptions, multi-tenant auth product, custom CDN domain (optional later), A10G migration unless T4 is insufficient after intent-based warm-up, 24/7 `min_containers` (too expensive).

### Current progress

| Status | Steps |
|--------|--------|
| **Done** | **1** — structured logging & per-stage timing |
| **Done** | **2** — intent-based GPU warm-up (`POST /warm`, file select, `scaledown_window=120`) |
| Not started | **3–8** — see [step-by-step](#step-by-step-execution-order) |

**Production today:** https://automatic-karaoke.vercel.app → Modal API → GPU pipeline → R2 `video_url` ([Phase 6](./PHASE_6.md) complete).

**Deployed API:** https://jacoblum22--karaoke-api.modal.run

**Known gaps carried from Phase 6:**

| Gap | Phase 7 target |
|-----|----------------|
| Cold GPU path ~153s (Psychosomatic) | **File-select warm-up** + `scaledown_window=120`; per-stage timing logs |
| Upload blocks on full multipart to Modal | Optional presigned R2 upload (Step 6) |
| No rate limits / abuse controls | Per-IP or global limits on `start-job` |
| R2 + Volume + Dict grow forever | TTL cleanup for jobs and artifacts |
| Sparse production logs | Structured `job_id` + stage logs |

---

## Entry criteria

Before starting Phase 7:

- [ ] [Phase 6 exit](./PHASE_6.md#exit-criteria--phase-7) satisfied
- [ ] `scripts/smoke_pipeline_modal.py` passes on deployed API
- [ ] `scripts/smoke_phase6_step8.py --verify-only` passes (Vercel → Modal)
- [ ] Modal secret **`karaoke-r2`** linked; production jobs return real R2 URLs
- [ ] `modal deploy` from `backend/` succeeds; `modal profile current` shows your account

**Critical rules (unchanged from Phase 6):**

1. **Pipeline order:** Demucs → transcribe on **vocals** → render on **instrumental** + `lyrics.json`.
2. **Upload before work:** Persist input to Volume **before** `run_real_pipeline.spawn`.
3. **Do not regress** Phase 3–6 isolation smokes after each hardening change.

---

## Architecture (Phase 7 additions)

Phase 7 wraps the Phase 6 pipeline with **operations** layers — not a new ML path.

```text
Browser
  │  User selects audio file → POST /warm (fire-and-forget)
  │       → Demucs + Whisper containers load models (GPU warm-up in parallel with browse/upload)
  │  POST /start-job multipart → Modal → Volume
  │  (Step 6 optional) presigned PUT to R2 → notify Modal with job_id
  ▼
Modal karaoke_api (rate limit, max duration check)
  ▼
run_real_pipeline(job_id)     ← GPU fns use scaledown_window=120 (2 min idle)
  │  log: stage_start / stage_end / gpu_seconds
  ▼
R2 karaoke/{job_id}/karaoke.mp4
  ▼
TTL cron / on-read cleanup     ← R2 object, Volume dir, Dict row (24h)
```

**Warm-up policy (v1):**

1. **Trigger:** frontend calls `POST /warm` when the user **selects a file** (not on bare page load — avoids warming every visitor).
2. **Idle retention:** `scaledown_window=120` on GPU functions — containers stay up **2 minutes** after last activity, then scale to zero.
3. **No upload in 2 min:** GPUs shut down; next upload pays cold start unless user selects a file again (re-triggers `/warm`).
4. **No 24/7 pool:** do **not** use `min_containers=1` for personal/demo traffic (~$14/day per T4).

**What stays the same:**

| Component | Phase 6 behavior | Phase 7 change |
|-----------|------------------|----------------|
| `_DEMUCS_IMAGE` / `_WHISPER_IMAGE` | T4 GPU; scale to zero when idle | `scaledown_window=120`; warmed via `POST /warm` on file select |
| `_RENDER_IMAGE` | CPU FFmpeg | Unchanged (cheap; cold OK) |
| `transcribe.py` | `large-v3`, `vad_filter=False` | No change unless tuning task |
| Frontend | Upload → `start-job` | File select → `warm` (async), then upload on submit |

---

## Target repository changes

```text
backend/
├── orchestrator.py          # stage timing logs; optional retry once on GPU failure
├── jobs.py                  # TTL helpers; optional expires_at on create_job
├── web.py                   # POST /warm; rate limit; max audio duration (ffprobe)
├── storage.py               # presigned POST/PUT helpers (Step 6); delete by prefix
├── job_storage.py           # delete_job_workspace (exists); volume sweeper
├── cleanup.py               # NEW — R2 + Volume + Dict TTL (cron + helpers)
└── app.py                   # warm_gpu fns; scaledown_window on GPU fns; cleanup cron

frontend/
├── src/api/client.ts        # warmPipeline() on file select
└── src/components/UploadForm.tsx  # call warm when file chosen

scripts/
├── smoke_phase7_step1.py    # timing logs present in Modal output
├── smoke_phase7_step2.py    # file-select warm → faster E2E vs cold baseline
├── smoke_phase7_step3.py    # reject >8 min audio
├── smoke_phase7_step4.py    # cleanup removes old job artifacts
├── smoke_phase7_step5.py    # rate limit returns 429
└── smoke_phase7_step6.py    # presigned upload path (optional)

docs/
└── PHASE_7.md               # this file
```

**Modal additions:**

| Function | Schedule | Purpose |
|----------|----------|---------|
| `warm_gpu_pipeline` | HTTP `POST /warm` | Load Demucs + Whisper models when user selects a file |
| `cleanup_expired_jobs` | `@app.function` + `modal.Period(hours=6)` or daily | Sweep R2 + Volume + Dict |
| (optional) `issue_upload_url` | web endpoint | Presigned PUT URL for input audio |

---

## Defaults & policy (v1 recommendations)

| Policy | Value | Notes |
|--------|--------|--------|
| Max upload size | 50 MB | Already in `web.py` |
| Max song duration | **8 minutes** | Reject after upload via ffprobe (Step 3) |
| Job TTL | **24 hours** | Dict row + R2 + Volume workspace |
| Rate limit | e.g. **5 jobs / hour / IP** | Tune for demo vs public launch |
| GPU idle window | **`scaledown_window=120`** (2 min) | On `separate_stems`, `transcribe_vocals_modal` |
| Warm trigger | **`POST /warm` on file select** | Overlaps model load with browse + upload time |
| Warm latency target | **&lt;90s** wall for ~3 min song (with warm) | Phase 6 logged 153s cold |
| Production R2 cleanup | **Yes** for jobs older than TTL | Smokes still self-clean (Phase 6) |
| Auth | **Optional** (Step 7) | API key header or defer to v2 |

---

## Step-by-step execution order

Complete in order. Each **Gate** must pass before the next step unless noted as optional.

### Step 1 — Structured logging & per-stage timing

| # | Action |
|---|--------|
| 1.1 | Add `log_job_event(job_id, stage, event, **fields)` helper (stdout JSON or key=value) |
| 1.2 | Log at start/end of each orchestrator stage: `separating`, `transcribing`, `rendering`, `upload` |
| 1.3 | Record `elapsed_s` per stage; log total wall time on `done` / `failed` |
| 1.4 | Optional: log approximate input duration (ffprobe on `input.*`) |

**Gate:**

- [x] `scripts/smoke_phase7_step1.py` — skeleton pipeline logs `job_id` + stage boundaries
- [ ] Optional E2E: `scripts/smoke_pipeline_modal.py` then `modal app logs karaoke` (includes `upload`)

**First testable point:** observability without behavior change.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_phase7_step1.py --deploy
# Full E2E: scripts\smoke_pipeline_modal.py then modal app logs karaoke (filter by job_id)
```

---

### Step 2 — Intent-based GPU warm-up (file selected)

| # | Action |
|---|--------|
| 2.1 | Add `POST /warm` on `karaoke_api` — no body required; idempotent; returns `202` quickly |
| 2.2 | Implement `warm_gpu_pipeline` in `app.py` — lightweight calls that load Demucs + Whisper models (e.g. `.remote()` on small warm helpers or import + noop on each image) |
| 2.3 | Set `scaledown_window=120` on `separate_stems` and `transcribe_vocals_modal` (2 min idle, then scale to zero) |
| 2.4 | Frontend: in `UploadForm`, on valid file select, call `warmPipeline()` fire-and-forget (ignore errors) |
| 2.5 | Document cost tradeoff in this file and README (~$0.07/bounce if user selects file but never uploads) |
| 2.6 | Compare E2E wall time: cold (no `/warm`) vs file-select warm → upload within 2 min |

**Gate:**

- [x] Selecting a file triggers `/warm` (network tab); no warm on page load alone
- [ ] E2E with file-select warm finishes **faster** than cold baseline (log both; `--compare-e2e`)
- [ ] If user waits &gt;2 min after warm without uploading, next job behaves cold unless they re-select file
- [ ] Phase 3–5 Modal smokes still pass

**Second testable point:** intent-based warm path.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_phase7_step2.py --deploy
.\.venv\Scripts\python.exe scripts\smoke_pipeline_modal.py --warm --warm-wait 45
# Optional cold vs warm comparison (~2× E2E runtime):
.\.venv\Scripts\python.exe scripts\smoke_phase7_step2.py --compare-e2e
```

---

### Step 3 — Max audio duration (8 minutes)

| # | Action |
|---|--------|
| 3.1 | After upload lands on Volume, ffprobe `input.*` duration |
| 3.2 | If duration &gt; 480s: `set_failed` with clear message; do not spawn pipeline |
| 3.3 | Return `400` or fail job early with `error` visible in `job-status` |
| 3.4 | Frontend: surface `error` (already shown via `ProgressTracker`) |

**Gate:**

- [ ] &gt;8 min fixture rejected with readable error
- [ ] Psychosomatic (~3 min) still completes

**Third testable point:** duration guardrail.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_phase7_step3.py --deploy
.\.venv\Scripts\python.exe scripts\smoke_phase7_step3.py
```

---

### Step 4 — TTL cleanup (R2, Volume, Dict)

| # | Action |
|---|--------|
| 4.1 | Extend `storage.py` with `delete_karaoke_mp4` (exists) + optional prefix list |
| 4.2 | Reuse `delete_job_workspace` from `job_storage.py` |
| 4.3 | `delete_job` in `jobs.py` for Dict row |
| 4.4 | Implement `cleanup_expired_jobs(max_age_hours=24)` — scan Dict `created_at` or R2 listing |
| 4.5 | Schedule Modal cron **or** run cleanup on successful `done` after N hours (cron preferred for orphans) |
| 4.6 | **Do not** delete in-flight jobs; skip `queued` / active statuses |

**Gate:**

- [ ] Synthetic old `job_id` artifacts removed by cleanup function
- [ ] Fresh job unaffected
- [ ] Cloudflare R2 bucket does not grow unbounded from production traffic

**Fourth testable point:** storage lifecycle.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_phase7_step4.py --deploy
.\.venv\Scripts\python.exe scripts\smoke_phase7_step4.py
```

**Alternative (no code):** Cloudflare R2 lifecycle rule — delete `karaoke/` objects after 7 days. Document in README; still implement Dict/Volume cleanup in code.

---

### Step 5 — Rate limiting on `start-job`

| # | Action |
|---|--------|
| 5.1 | Track requests per IP (in-memory dict on container — best-effort) or Modal Dict counter |
| 5.2 | Return `429 Too Many Requests` when over limit |
| 5.3 | Document limits in API error message and README |
| 5.4 | Exempt health/smoke paths if needed |

**Gate:**

- [ ] Burst of test requests hits 429
- [ ] Normal single upload still works

**Fifth testable point:** abuse guardrail.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_phase7_step5.py
```

---

### Step 6 — Presigned R2 upload (optional, larger change)

**Defer if** multipart upload is acceptable for v1 demo.

| # | Action |
|---|--------|
| 6.1 | New endpoint `POST /upload-url` → `{ job_id, upload_url, fields? }` (S3 presigned PUT/POST) |
| 6.2 | Browser uploads audio **directly to R2** `uploads/{job_id}/input.mp3` |
| 6.3 | `POST /start-job` becomes `{ job_id }` only — Modal copies R2 → Volume or reads from R2 |
| 6.4 | Frontend: show upload progress % (XHR/fetch progress on PUT) |
| 6.5 | CORS on R2 bucket for Vercel origin |

**Gate:**

- [ ] Large file (e.g. 20 MB) upload does not block Modal HTTP handler for full transfer
- [ ] E2E still produces real `video_url`

**Sixth testable point:** faster uploads for large MP3s.

---

### Step 7 — Optional auth (API key)

| # | Action |
|---|--------|
| 7.1 | Modal secret `karaoke-api-key` with `API_KEY` |
| 7.2 | Require header `X-API-Key` on `start-job` (and upload-url if Step 6) |
| 7.3 | Vercel env `VITE_API_KEY` for frontend (public — only for private demo) |

**Note:** A key embedded in the frontend is **not secret**; real auth needs a backend proxy or user login (v2). For private beta, optional.

**Gate:**

- [ ] Requests without key get `401`
- [ ] Valid key allows pipeline

---

### Step 8 — Regression, docs, sign-off

| # | Action |
|---|--------|
| 8.1 | Run Phase 6 E2E + Phase 3–5 Modal smokes |
| 8.2 | Update `README.md`, `IMPLEMENTATION_PLAN.md`, `AGENTS.md` |
| 8.3 | Mark Phase 7 checklist; note warm-up cost model in README |
| 8.4 | Commit + push; verify Vercel + Modal deploy |

**Gate:**

- [ ] No regression on https://automatic-karaoke.vercel.app
- [ ] Phase 7 checklist complete

**Eighth testable point:** hardened production baseline.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_pipeline_modal.py
.\.venv\Scripts\python.exe scripts\smoke_phase6_step8.py --verify-only
.\.venv\Scripts\python.exe scripts\smoke_demucs_modal.py
.\.venv\Scripts\python.exe scripts\smoke_whisper_modal.py
.\.venv\Scripts\python.exe scripts\smoke_render_modal.py
```

---

## Phase 7 completion checklist

**Required for Phase 7 exit** (Steps 1–5 + 8; Steps 6–7 optional but documented if skipped):

### Performance

- [ ] Per-stage timing logs in Modal for production jobs
- [ ] `POST /warm` on file select + `scaledown_window=120` on GPU functions
- [ ] Warm E2E wall time measured vs cold baseline (target &lt;90s for ~3 min song when warm, or justified)

### Safety & cost

- [ ] Max duration enforced (~8 min)
- [ ] Rate limit on `start-job`
- [ ] TTL cleanup for R2 + Volume + Dict (code or R2 lifecycle + code for Dict/Volume)

### Regression

- [ ] `smoke_pipeline_modal.py` passes
- [ ] Phase 3–5 Modal smokes pass
- [ ] Live site still plays returned MP4

### Explicitly optional (document if deferred)

- [ ] Presigned browser → R2 upload
- [ ] API key / user auth
- [ ] Custom domain on R2 CDN
- [ ] Lyric editor / external lyric source

---

## Exit criteria → v2 / maintenance

Phase 7 is **complete** when:

1. [Completion checklist](#phase-7-completion-checklist) required items are checked.
2. Production jobs are **observable** (logs), **bounded** (duration + rate limit), and **cleaned up** (TTL).
3. Warm GPU latency is acceptable for demo use or documented with Modal metrics.
4. README states operational policies (limits, retention, warm-up cost model).

**After Phase 7:** product is suitable for **limited public beta**. Further work is feature v2 (lyric correction UI, accounts, payments) rather than pipeline wiring.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Warm-up cost too high | Do not use `min_containers`; warm only on file select; shorten `scaledown_window` |
| Still slow after warm | User may have waited &gt;2 min; re-select file to re-warm; check per-stage logs |
| `/warm` on every page view | Move trigger to file select only |
| Duration check false positive | ffprobe codec edge case; allow `.m4a` probe retry |
| Cleanup deleted active job | Only delete `done`/`failed` older than TTL; never delete in-flight status |
| Rate limit blocks dev testing | Whitelist localhost or raise limit in dev deploy |
| Presigned CORS fail | R2 bucket CORS for `automatic-karaoke.vercel.app` + `PUT` |
| R2 bucket still grows | Confirm cron runs; check lifecycle rule; smokes use `smoke_phase6_cleanup` |
| 429 in production | Expected under abuse; tune limits |

---

## Modal commands reference

```powershell
# Deploy after hardening changes
cd backend
..\.venv\Scripts\modal.exe deploy app.py

# E2E + timing
cd ..
.\.venv\Scripts\python.exe scripts\smoke_pipeline_modal.py

# Logs (structured lines after Step 1)
..\.venv\Scripts\modal.exe app logs karaoke

# Manual cleanup (after Step 4)
..\.venv\Scripts\modal.exe run app.py::cleanup_expired_jobs

# Cost / GPU metrics
# Modal dashboard → Apps → karaoke → Metrics
```

---

## Cost notes (intent-based warm-up)

Modal bills GPU **per second** while containers run or sit idle within `scaledown_window`. T4 ≈ **$0.59/hr** (~$0.000164/s). See [Modal pricing](https://modal.com/pricing).

| Scenario | Approx. cost |
|----------|----------------|
| **24/7 `min_containers=1` × 2 T4s** | ~**$28/day** — avoid for this project |
| **File select, no upload** (2 min idle × 2 GPUs) | ~**$0.06–0.08** per bounce |
| **Real job** (GPU compute only) | ~**$0.02–0.05** (you pay this anyway) |
| **Low traffic** (5 bounces + 5 jobs/day) | ~**$0.50–0.80/day** |

Warm-on-file-select trades a few cents of idle GPU for overlapping model load with the time users spend choosing and uploading a file — usually better UX than 24/7 warm or fully cold starts.

Document measured costs in README when Step 2 ships.

---

## Reference: warm-up + `scaledown_window` sketch

```python
# backend/web.py — new route
@api.post("/warm")
async def warm_pipeline():
    warm_gpu_pipeline.spawn()  # fire-and-forget
    return {"status": "warming"}


# backend/app.py
@app.function(image=_DEMUCS_IMAGE, gpu="T4", scaledown_window=120, timeout=600)
def separate_stems(...):
    ...

@app.function(image=_WHISPER_IMAGE, gpu="T4", scaledown_window=120, timeout=1200)
def transcribe_vocals_modal(...):
    ...

@app.function(image=_BACKEND_IMAGE)
def warm_gpu_pipeline() -> None:
    # Trigger model load on both GPU images (implementation TBD in Step 2)
    _demucs_warm.remote()
    _whisper_warm.remote()
```

```typescript
// frontend — on file select (after validateAudio passes)
void warmPipeline().catch(() => {});
```

## Reference: cleanup sketch

```python
@app.function(
    schedule=modal.Period(hours=6),
    secrets=[R2_SECRET],
    volumes={JOBS_MOUNT: JOBS_VOL},
)
def cleanup_expired_jobs(max_age_hours: int = 24) -> dict:
    # For each job in Dict older than max_age_hours:
    #   delete_karaoke_mp4(job_id)
    #   delete_job_workspace(job_id, JOBS_VOL)
    #   delete_job(job_id)
    ...
```

---

## Lessons from Phase 6 (inputs to Phase 7)

| Topic | Observation | Phase 7 action |
|-------|-------------|----------------|
| Cold start | ~153s wall for Psychosomatic E2E | File-select `/warm` + `scaledown_window=120` |
| Upload UX | Browser blocks until full file on Modal | Presigned upload (optional) |
| R2 growth | Smoke cleanup exists; production does not | TTL cron |
| Wrong lyrics | ASR limitation on sung vocals | Out of scope — not a hardening task |
| `r2.dev` verify | Modal egress 403; local verify OK | No change needed |
| `sample_30s.mp3` | Tone breaks Whisper | Duration/upload docs only |

---

*Phase 7 runbook v1.1 — intent-based GPU warm-up (file select), 2 min scaledown.*
