# Phase 6 — Integrate ML Pipeline (Backend)

**Parent doc:** [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)  
**Prerequisite:** [PHASE_5.md](./PHASE_5.md) exit criteria (local + Modal render smokes; stub API unchanged)  
**Estimated time:** 16–30 hours (Volume + cross-image orchestration + R2 + E2E debugging)  
**Goal:** Replace the Phase 2 **stub orchestrator** with a real pipeline: user upload → Demucs → transcribe+align → render → **real MP4 URL** on `job-status`. Minimal frontend change (play `video_url` when done).

**Out of scope for Phase 6:** Presigned R2 upload from browser, auth/payments, rate limits, `keep_warm` tuning (Phase 7), lyric accuracy improvements (Phase 4 tuning / v2 lyric sources).

### Current progress

| Status | Steps |
|--------|--------|
| Done | **1–8** ✓ (Step 8: verify production bundle; redeploy frontend for subtitle) |

**Production today:** https://automatic-karaoke.vercel.app — API runs full pipeline through R2 when secret `karaoke-r2` is configured.

**Deployed API:** https://jacoblum22--karaoke-api.modal.run

**Next after Phase 6:** [Phase 7 — Production hardening](./IMPLEMENTATION_PLAN.md#phase-7--production-hardening) — presigned uploads, `keep_warm`, observability, production R2 TTL.

---

## Entry criteria

Before starting Phase 6:

- [ ] [Phase 5 exit](./PHASE_5.md#exit-criteria--phase-6) satisfied
- [ ] Phases 3–5 isolation smokes pass on **Psychosomatic** pair (recommended quality baseline)
- [ ] `modal profile current` shows your account; `modal deploy` works from `backend/`
- [ ] **Cloudflare R2** (or S3-compatible) bucket created; credentials ready for `modal.Secret` (not in git)
- [ ] Python venv (`.venv`) active

**Critical rules:**

1. **Order:** Demucs → transcribe on **vocals** → render on **instrumental** + `lyrics.json`. Never transcribe the full mix.
2. **Upload before work:** `POST /start-job` must persist audio to job storage **before** the pipeline reads it (today the stub spawns first, then drains the body — Phase 6 fixes this).
3. **Same job directory:** All stages for one `job_id` must read/write the same paths (Modal Volume recommended).

---

## Architecture (target)

```text
Browser  POST /start-job (multipart audio)
              ↓
         save → /jobs/{job_id}/input.{ext}     (Volume or /tmp; commit)
              ↓
         spawn run_real_pipeline(job_id)
              ↓
    ┌─────────────────────────────────────────────────────────┐
    │  orchestrator (Modal, updates jobs.py / modal.Dict)      │
    │    1) separating  → separate_stems (GPU, _DEMUCS_IMAGE)   │
    │         → vocals.wav, instrumental.wav                   │
    │    2) transcribing + aligning → transcribe_vocals_modal    │
    │         (GPU, _WHISPER_IMAGE) → lyrics.json              │
    │    3) rendering → render_karaoke_modal (CPU, _RENDER_IMAGE)│
    │         → karaoke.mp4                                    │
    │    4) upload → storage.py → R2 signed/public URL          │
    │    5) done → video_url on job record                     │
    └─────────────────────────────────────────────────────────┘
              ↓
Browser  GET /job-status?job_id=…  →  video_url = real MP4
```

**Modal images (already split — keep):**

| Image | Functions | GPU |
|-------|-----------|-----|
| `_BACKEND_IMAGE` | `karaoke_api`, `jobs`, orchestrator spawn | No |
| `_DEMUCS_IMAGE` | `separate_stems`, Demucs smokes | T4 |
| `_WHISPER_IMAGE` | `transcribe_vocals_modal`, whisper smokes | T4 |
| `_RENDER_IMAGE` | `render_karaoke_modal`, render smokes | No (CPU) |

Orchestrator should call existing Modal functions via `.remote()` (or a dedicated coordinator function with Volume mounts on each callee).

---

## Per-job workspace layout

Mount a shared Volume at `/jobs` (name e.g. `karaoke-job-data`):

```text
/jobs/{job_id}/
  input.mp3              # uploaded audio (original mix)
  vocals.wav             # Demucs out
  instrumental.wav       # Demucs out
  lyrics.json            # Phase 4 contract
  karaoke.mp4            # Phase 5 out
```

After each stage that writes files, call `volume.commit()` so the next container sees updates.

**Job record** (`modal.Dict` `karaoke-jobs`) — existing fields from [PHASE_2](./PHASE_2.md):

| Field | Phase 6 usage |
|-------|----------------|
| `status` | `queued` → `separating` → `transcribing` → `aligning` → `rendering` → `done` / `failed` |
| `progress` | 0 → 20 → 40 → 60 → 80 → 100 |
| `message` | Human-readable stage text |
| `video_url` | **Real** R2 (or CDN) URL to `karaoke.mp4` |
| `error` | Set on failure; status `failed` |

---

## Target repository changes

```text
backend/
├── job_storage.py           # Volume paths + write/commit helpers
├── orchestrator.py          # replace stub: run_real_pipeline(job_id)
├── storage.py               # implement upload_file → URL
├── web.py                   # save upload before spawn; optional max duration check
├── app.py                   # Volume mount; wire spawn to real pipeline
│                            # optional: run_real_pipeline @function with volumes
└── .env.example             # document R2 secret keys (Modal Secret names)

scripts/
├── smoke_phase6_step1.py    # upload → Volume verify
├── smoke_pipeline_modal.py  # E2E: upload fixture → poll → assert real video_url
└── smoke_phase6_step*.py    # optional granular gates (see below)

docs/
└── PHASE_6.md               # this file
```

**Reuse (no reimplementation):**

| Module | Entrypoint |
|--------|------------|
| `separate.py` | `separate_audio()` — used by `separate_stems` |
| `transcribe.py` | `transcribe_and_align()` — used by `transcribe_vocals_modal` |
| `render.py` | `render_karaoke()` — used by `render_karaoke_modal` |

**Defaults (v1 recommendations):**

| Setting | Value | Notes |
|---------|--------|--------|
| Demucs | `htdemucs`, `--two-stems=vocals` | Same as Phase 3 |
| Whisper | `large-v3` | Production default (accuracy over latency) |
| `vad_filter` | `False` | Project default — vocal stem already isolated |
| Render | 1080p, ASS burn-in | Phase 5 `render_karaoke` |

---

## Modal secrets & R2

Create a Modal secret (example name `karaoke-r2`):

| Key | Purpose |
|-----|---------|
| `R2_ACCESS_KEY_ID` | S3-compatible access key |
| `R2_SECRET_ACCESS_KEY` | Secret |
| `R2_BUCKET` | Bucket name |
| `R2_ENDPOINT_URL` | e.g. `https://<account>.r2.cloudflarestorage.com` |
| `R2_PUBLIC_BASE_URL` | Optional CDN/public base for `video_url` |

Wire secret on pipeline functions after the secret exists (or link **karaoke-r2** to the `karaoke` app in the Modal dashboard):

```python
R2_SECRET = modal.Secret.from_name("karaoke-r2")

@app.function(secrets=[R2_SECRET], ...)
def run_real_pipeline(...):
    ...
```

`app.py` wires `secrets=[R2_SECRET]` on `run_real_pipeline` and R2 smokes after the secret exists (create/link **karaoke-r2** in Modal before deploy).

**v1 fallback (dev only):** If R2 is not ready, document a temporary `video_url` strategy (e.g. Modal volume download endpoint) — **production uses R2 public URLs**.

**Smoke cleanup:** Phase 6 smokes delete R2 objects and Volume job dirs when finished (`smoke_phase6_cleanup`). Production jobs are not auto-deleted.

---

## Step-by-step execution order

Complete in order. Each **Gate** must pass before the next step.

### Step 1 — Job storage + upload fix

| # | Action |
|---|--------|
| 1.1 | Define `modal.Volume` + path helpers (`job_dir(job_id)`) |
| 1.2 | Change `start-job`: drain upload → write `input.*` → `volume.commit()` → **then** `spawn_pipeline(job_id)` |
| 1.3 | Smoke: upload `sample_30s.mp3` lands on Volume with correct size |

**Gate:**

- [x] File exists at `/jobs/{job_id}/input.mp3` (or `.wav`) before pipeline starts
- [x] Upload drained and committed before `spawn_pipeline` (job stays `queued` until save completes)

**First testable point:** persisted upload only.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_phase6_step1.py --deploy
.\.venv\Scripts\python.exe scripts\smoke_phase6_step1.py
```

---

### Step 2 — Real orchestrator skeleton

| # | Action |
|---|--------|
| 2.1 | Add `run_real_pipeline(job_id)` in `orchestrator.py` |
| 2.2 | Replace `run_stub_pipeline.spawn` with real pipeline in `app.py` (feature flag or full swap) |
| 2.3 | On failure: `set_failed(job_id, ...)`; no `done` without `video_url` |

**Gate:**

- [x] Pipeline advances Dict statuses in order (even if stages no-op initially)
- [x] Simulated exception → `failed` + `error` message

**Second testable point:** job lifecycle without ML.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_phase6_step2.py --deploy
```

---

### Step 3 — Wire Demucs (separate)

| # | Action |
|---|--------|
| 3.1 | Orchestrator calls `separate_stems.remote(input, workdir, device="cuda")` with Volume paths |
| 3.2 | Verify `vocals.wav` + `instrumental.wav` non-empty; `volume.commit()` |
| 3.3 | Update progress: `separating` / 20% |

**Gate:**

- [x] One job produces stems on Volume
- [x] Durations match input (± padding)

**Third testable point:** separation inside pipeline.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_phase6_step3.py --deploy
```

---

### Step 4 — Wire transcribe + align

| # | Action |
|---|--------|
| 4.1 | Call `transcribe_vocals_modal.remote(vocals_path, lyrics_path, clip_end=None, ...)` |
| 4.2 | Validate `lyrics.json` with `validate_lyrics_json.py` logic (in-container or after download) |
| 4.3 | Progress: `transcribing` 40%, `aligning` 60% (or combine message) |

**Gate:**

- [x] `lyrics.json` exists and passes contract
- [x] Failed transcribe → job `failed` (no render) — `simulate_fail` before Whisper remote

**Fourth testable point:** lyrics on Volume.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_phase6_step4.py --deploy
```

---

### Step 5 — Wire render

| # | Action |
|---|--------|
| 5.1 | Call `render_karaoke_modal.remote(instrumental, lyrics, output_mp4)` |
| 5.2 | Progress: `rendering` / 80% |
| 5.3 | Output `karaoke.mp4` non-zero |

**Gate:**

- [x] MP4 plays locally if copied from Volume (optional manual)
- [x] Render failure → job `failed`

**Fifth testable point:** MP4 on Volume without R2.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_phase6_step5.py --deploy
```

---

### Step 6 — R2 upload + `video_url`

| # | Action |
|---|--------|
| 6.1 | Implement `storage.upload_karaoke_mp4(local_path, job_id) -> str` URL |
| 6.2 | Orchestrator sets `video_url` on `done` |
| 6.3 | Object key scheme e.g. `karaoke/{job_id}/karaoke.mp4` |

**Gate:**

- [x] URL is HTTPS and downloadable
- [x] Pipeline sets `done` + real URL (not `sample.mp4`)

**Sixth testable point:** deliverable URL.

```powershell
# Create secret once: modal secret create karaoke-r2 R2_ACCESS_KEY_ID=... ...
.\.venv\Scripts\python.exe scripts\smoke_phase6_step6.py --deploy
.\.venv\Scripts\python.exe scripts\smoke_phase6_step6.py --upload-only
```

Smokes verify the URL from your machine (r2.dev often blocks Modal egress) and **delete the R2 object** when done.

---

### Step 7 — End-to-end API smoke

| # | Action |
|---|--------|
| 7.1 | `scripts/smoke_pipeline_modal.py` — POST audio to deployed API, poll to `done` |
| 7.2 | Assert `video_url` host is R2/CDN, not Vercel `sample.mp4` |
| 7.3 | `modal deploy`; regression: existing Phase 2–5 smokes still pass |

**Gate:**

- [x] One real song completes via API only (curl or script)
- [ ] Total time **&lt; 90s** on warm T4 for ~3 min song (target; **153s** logged on cold run with Psychosomatic — acceptable for v1)
- [x] Failed Demucs does not leave orphan `done` status (orchestrator sets `failed` on exception)

**Seventh testable point:** full stack without manual steps.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_pipeline_modal.py --deploy
.\.venv\Scripts\python.exe scripts\smoke_pipeline_modal.py
```

Uses ``Psychosomatic.mp3`` by default (real vocals; ~10–25 min wall time on cold GPU). Cleans up R2 + Volume after verify.

---

### Step 8 — Frontend + docs sign-off

| # | Action |
|---|--------|
| 8.1 | Confirm Vercel `VITE_API_URL` points at deployed Modal API |
| 8.2 | Upload on production/preview plays returned MP4 |
| 8.3 | Mark checklist; update `README.md`, `IMPLEMENTATION_PLAN.md` |
| 8.4 | Commit + push when ready |

**Gate:**

- [x] Browser upload → progress stages → real karaoke video (verified via Step 7 + client smoke; manual on Vercel after deploy)
- [x] Phase 6 checklist complete

**Eighth testable point:** user-visible karaoke on the live site.

```powershell
# Fast — live Vercel bundle uses Modal API (not mock)
.\.venv\Scripts\python.exe scripts\smoke_phase6_step8.py --verify-only

# Full — same path as the React duplicates (client.ts → Modal → R2), ~10–25 min
cd frontend
npm run smoke:modal
cd ..
.\.venv\Scripts\python.exe scripts\smoke_phase6_step8.py --full
```

After `App.tsx` subtitle change, **redeploy frontend** (`git push main` or `vercel --prod` from `frontend/`) so https://automatic-karaoke.vercel.app shows the updated copy.

---

## Phase 6 completion checklist

**All required boxes** must be checked before [Phase 7](./IMPLEMENTATION_PLAN.md#phase-7--production-hardening).

### Pipeline

- [x] Upload persisted before pipeline spawn
- [x] `run_real_pipeline` calls separate → transcribe → render in order
- [x] Shared Volume (or equivalent) across stages
- [x] Failures set `status=failed` with `error`; no false `done`

### Storage & API

- [x] `storage.py` uploads MP4 to R2 (or documented production URL strategy)
- [x] `video_url` on completed jobs is the generated karaoke file
- [x] `smoke_pipeline_modal.py` passes on deployed app

### Performance (reference)

- [x] Log wall time per stage + total for ~3 min song (Step 7 smoke logs total wall time)
- [ ] Warm GPU path meets or documents gap vs &lt;90s target (153s cold; Phase 7 `keep_warm`)

### Explicitly NOT done (confirm)

- [x] No presigned browser → R2 upload (still multipart to Modal)
- [x] No auth / rate limits
- [x] No `keep_warm` (Phase 7)
- [x] Lyric text accuracy not re-opened (Phase 4 concern)

---

## Exit criteria → Phase 7

Phase 6 is **complete** when:

1. [Completion checklist](#phase-6-completion-checklist) required items are checked.
2. `POST /start-job` with real audio → poll → **`video_url`** serves the generated karaoke MP4.
3. Vercel app plays that URL in `VideoPlayer` without code changes beyond env verification (or minimal URL handling if needed).
4. Stub `STUB_VIDEO_URL` path removed or unreachable in production orchestrator.

**Next:** [Phase 7 — Production hardening](./IMPLEMENTATION_PLAN.md#phase-7--production-hardening).

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Pipeline starts before upload finishes | Step 1 — spawn only after drain + Volume commit |
| Next stage cannot find stems | `volume.commit()` after writes; same mount path on all functions |
| `CUDA OOM` | Shorter clip; `medium` not `large-v3`; T4 |
| `done` but `sample.mp4` | Orchestrator still stub; check `app.py` spawn target |
| R2 403 / wrong URL | Secret keys, bucket CORS, `R2_PUBLIC_BASE_URL` |
| Lyrics wrong in video | Phase 4 ASR — not orchestrator; tune model separately |
| Cold start &gt;90s | Expected first run; Phase 7 `keep_warm`; log per-stage times |
| `sample_30s.mp3` in Step 7 E2E | Whisper fails (tone, no speech) | Use `Psychosomatic.mp3` (default in `smoke_pipeline_modal.py`) |
| CORS on `video_url` | R2 public access or CDN; separate from Modal API CORS |

---

## Modal commands reference

```powershell
# Deploy all functions (API + ML + render)
cd backend
..\.venv\Scripts\modal.exe deploy app.py

# E2E (after smoke script exists)
cd ..
.\.venv\Scripts\python.exe scripts\smoke_pipeline_modal.py --deploy

# Logs
..\.venv\Scripts\modal.exe app logs karaoke

# Isolation regressions (should still pass)
.\.venv\Scripts\python.exe scripts\smoke_demucs_modal.py
.\.venv\Scripts\python.exe scripts\smoke_whisper_modal.py
.\.venv\Scripts\python.exe scripts\smoke_render_modal.py
```

---

## Reference: orchestrator shape (sketch)

```python
def run_real_pipeline(job_id: str) -> None:
    work = Path(f"/jobs/{job_id}")
  try:
        update_job(job_id, status="separating", progress=20, message="Separating vocals…")
        separate_stems.remote(str(work / "input.mp3"), str(work), device="cuda")

        update_job(job_id, status="transcribing", progress=40, message="Transcribing vocals…")
        transcribe_vocals_modal.remote(
            str(work / "vocals.wav"),
            str(work / "lyrics.json"),
            clip_end=None,
            model_size="large-v3",
        )

        update_job(job_id, status="rendering", progress=80, message="Rendering karaoke video…")
        render_karaoke_modal.remote(
            str(work / "instrumental.wav"),
            str(work / "lyrics.json"),
            str(work / "karaoke.mp4"),
        )

        url = upload_karaoke_mp4(work / "karaoke.mp4", job_id)
        update_job(job_id, status="done", progress=100, message="Complete!", video_url=url)
    except Exception as exc:
        set_failed(job_id, str(exc))
```

Adjust paths, Volume commits, and `.remote()` mounts to match your `app.py` layout.

---

*Phase 6 runbook v1.0 — integrate Demucs, Whisper, and render into the Modal job pipeline.*
