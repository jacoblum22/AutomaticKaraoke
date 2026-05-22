# Phase 3 — Demucs in Isolation

**Parent doc:** [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)  
**Prerequisite:** [PHASE_2.md](./PHASE_2.md) complete (Modal API shell, stub orchestrator)  
**Estimated time:** 8–16 hours (longer if no local GPU; first Demucs install is slow)  
**Goal:** Given a mixed audio file, produce **two WAV stems** — **vocals** (for Phase 4 transcription) and **instrumental** (for Phase 5 render). Prove it **locally** and on **Modal GPU** before touching the full job orchestrator or frontend.

**Out of scope for Phase 3:** faster-whisper, WhisperX, FFmpeg, R2 uploads, wiring Demucs into `orchestrator.py` / `start-job`, frontend changes, real karaoke MP4 from user uploads.

### Current progress

| Status | Steps |
|--------|--------|
| Done | **1** fixture + Demucs deps — first testable point ✓ |
| Done | **2** `separate.py` + local stems — second testable point ✓ |
| Done | **3** `test_demucs_local.py` CLI + timing — third testable point ✓ |
| Done | **4** `vocals_30s.wav` fixture for Phase 4 — fourth testable point ✓ |
| Done | **5** Modal GPU `smoke_demucs_separate` — fifth testable point ✓ |
| Done | **6** `modal deploy` + deployed smoke — sixth testable point ✓ |
| Done | **7** full-song quality smoke (`Psychosomatic.mp3`) — seventh testable point ✓ |
| Done | **8** docs + README + plan sign-off — **Phase 3 complete** ✓ |

**Production API (unchanged):** https://automatic-karaoke.vercel.app still runs the **Phase 2 stub** pipeline until Phase 6 integration.

**Next after Phase 3:** [Phase 4 — Transcription + alignment](./IMPLEMENTATION_PLAN.md#phase-4--transcription--alignment-in-isolation-faster-whisper--whisperx) using `vocals.wav`.

---

## Entry criteria

Before starting Phase 3:

- [ ] [Phase 2 exit](./PHASE_2.md#exit-criteria--phase-3) satisfied (completion checklist + Modal smokes)
- [ ] `modal profile current` shows `jacoblum22`
- [ ] Python venv at repo root (`.venv`) with Phase 2 deps installed
- [x] **Fixture audio:** `sample_30s.mp3` (synthetic, committed) or run `scripts/generate_sample_fixture.py` — see [fixtures](#fixtures-and-git)
- [ ] Optional: NVIDIA GPU locally (CPU Demucs works but can take several minutes on 30s)
- [ ] Disk space for torch + Demucs models (~2–4 GB first download)

**Do not** require frontend or Vercel changes in this phase.

---

## Architecture (Phase 3 — isolation only)

```text
sample_30s.mp3  (fixtures/)
       ↓
┌──────────────────────────────────────┐
│  Local: scripts/test_demucs_local.py │
│  Modal: separate_stems @app.function │
│         (demucs_image, GPU T4)       │
└──────────────────────────────────────┘
       ↓
separate.py  — shared Demucs logic (paths in, paths out)
       ↓
scripts/output/vocals.wav
scripts/output/instrumental.wav
       ↓
(optional) copy vocals → scripts/fixtures/vocals_30s.wav  for Phase 4
```

**Critical rule:** Transcription in Phase 4 runs on **`vocals.wav` only**, not the full mix. Demucs quality directly affects lyric accuracy and sync.

**Not in Phase 3:**

```text
start-job → orchestrator → …   ← Phase 6
Browser upload → real stems    ← Phase 6
```

Phase 2 `orchestrator.py` keeps **sleep stubs** until integration.

| Layer | Phase 3 | Phase 6 |
|-------|---------|---------|
| `separate.py` | Real Demucs | Called from orchestrator |
| `orchestrator.py` | Unchanged stub | Calls separate → transcribe → render |
| `jobs.py` / web API | Unchanged | Real stage progress |
| Images | **`demucs_image`** (torch) separate from **`_BACKEND_IMAGE`** | Multiple images |

---

## Demucs settings (recommended)

| Setting | Value | Notes |
|---------|--------|--------|
| Model | `htdemucs` | Good speed/quality on T4 |
| Stems | `vocals` + `no_vocals` | `no_vocals` = instrumental bed |
| Output format | WAV, 44.1 kHz | Match downstream Whisper / FFmpeg expectations |
| Modal GPU | `T4` | ~20–40s per 3-min song when warm |
| Modal timeout | `600` s | Headroom for cold start + long uploads later |
| Local CPU | Acceptable for 30s fixture | Target &lt;5 min on laptop CPU |

**CLI reference (local sanity):**

```bash
python -m demucs.separate -n htdemucs --two-stems=vocals -o out/ input.mp3
# → out/htdemucs/<track>/vocals.wav, no_vocals.wav
```

Phase 3 wraps this (or the Demucs Python API) in `separate.py` so local script and Modal share one code path.

---

## Fixtures and git

| Path | Committed? | Purpose |
|------|------------|---------|
| `scripts/fixtures/sample_30s.mp3` | **Yes** (synthetic tone via ffmpeg) | Default test input; replace with your own mix if desired |
| `scripts/fixtures/sample_30s.wav` | **No** (gitignored, generated) | Source for MP3; regenerate with `generate_sample_fixture.py` |
| `scripts/fixtures/vocals_30s.wav` | **No** (gitignored; `save_vocal_fixture.py`) | Phase 4 default input |
| `scripts/output/` | **Gitignored** | Generated `vocals.wav`, `instrumental.wav` |

Add a `scripts/fixtures/README.md` note if helpful: “Place `sample_30s.mp3` here (30s, royalty-free).”

**Copyright:** Do not commit commercial masters; use royalty-free or self-recorded clips.

---

## Target repository tree (Phase 3 changes)

```text
backend/
├── requirements.txt              # unchanged for web API (modal + fastapi)
├── requirements-demucs.txt       (new) — torch, demucs; used by demucs_image only
├── separate.py                   (content) — run_demucs(input_path) -> (vocals, instrumental)
└── app.py                        (update) — DEMUCS_IMAGE, separate_stems fn, smoke_demucs

scripts/
├── fixtures/
│   ├── README.md                 (new) — how to add sample_30s.mp3
│   └── sample_30s.mp3            (local only)
├── output/                       vocals.wav, instrumental.wav (gitignored)
├── test_demucs_local.py          (content) — argparse, calls separate.py
└── smoke_demucs_modal.py         (new) — modal run / deploy smoke on GPU fn

docs/
└── PHASE_3.md                      (this file)
```

**Not created / not modified in Phase 3:**

| Path | Phase |
|------|-------|
| `frontend/` | 6 (optional progress copy only) |
| `orchestrator.py` real stages | 6 |
| `transcribe.py`, `render.py` | 4, 5 |
| `storage.py` R2 | 6/7 |

---

## File minimums

### `backend/separate.py`

- Docstring: input = path to mixed audio; output = paths to `vocals.wav` and `instrumental.wav`
- `separate_audio(input_path, output_dir) -> tuple[Path, Path]` — `htdemucs`, instrumental = sum of non-vocal stems
- Writes `vocals.wav` / `instrumental.wav` via stdlib `wave` (16-bit PCM @ model sample rate)
- Raise clear errors on missing file / Demucs failure (orchestrator will map to `failed` in Phase 6)
- **No** Modal imports in this module (pure Python for local + Modal image)

### `backend/requirements-demucs.txt`

```text
demucs>=4.0.0
torch>=2.0.0
# torchaudio if required by your demucs version
```

Install only on `demucs_image`, not on `_BACKEND_IMAGE` (keeps API cold starts small).

### `backend/app.py` (additions)

```python
_DEMUCS_IMAGE = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_requirements(_BACKEND_DIR / "requirements-demucs.txt")
    .add_local_dir(_BACKEND_DIR, remote_path="/root")
)

@app.function(image=_DEMUCS_IMAGE, gpu="T4", timeout=600)
def separate_stems(local_audio_path: str, job_output_dir: str) -> tuple[str, str]:
    """Returns (vocals_path, instrumental_path) on mounted volume."""
    ...
```

- Use a Modal **Volume** or `/tmp` under a job-scoped directory for outputs (document mount in Step 5)
- Smoke function: `smoke_demucs_separate` — runs on bundled or uploaded fixture path

### `scripts/test_demucs_local.py`

- Default input: `scripts/fixtures/sample_30s.mp3`
- Default output dir: `scripts/output/`
- Calls `separate.separate_audio` (add repo root / `backend` to `sys.path` or run as module)
- Prints paths and elapsed seconds; exit non-zero on failure
- Optional `--input` / `--output` flags

### `scripts/smoke_demucs_modal.py`

- `modal run app.py::smoke_demucs_separate` or deploy + remote call
- Asserts both output files exist and are non-empty
- Prints duration; exit 0 on success

---

## Step-by-step execution order

Complete in order. Each **Gate** must pass before the next step.

### Step 1 — Fixture + local dependencies

| # | Action |
|---|--------|
| 1.1 | Generate or add fixture: `python scripts/generate_sample_fixture.py` → `sample_30s.wav` (+ `sample_30s.mp3` if ffmpeg) |
| 1.2 | `backend/requirements-demucs.txt` (demucs, torch, torchaudio) |
| 1.3 | `pip install -r backend/requirements-demucs.txt` in `.venv` |
| 1.4 | Run Step 1 smoke |

**Gate:**

- [x] Fixture file exists (`sample_30s.wav` or `sample_30s.mp3`)
- [x] `import demucs, torch` succeeds in venv

**First testable point:** environment only — no separation yet.

```powershell
.\.venv\Scripts\python.exe scripts\generate_sample_fixture.py
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-demucs.txt
.\.venv\Scripts\python.exe scripts\smoke_phase3_step1.py
```

---

### Step 2 — Shared `separate.py` (pure Python)

| # | Action |
|---|--------|
| 2.1 | Implement `backend/separate.py` with `separate_audio(...)` |
| 2.2 | Unit smoke: call from `python -c` with fixture path into `scripts/output/` |

**Gate:**

- [x] Produces `vocals.wav` and `instrumental.wav` under output dir
- [x] Both files non-zero size (~5 MB each for 30s @ 44.1 kHz)
- [x] Vocal stem intelligible; instrumental usable as karaoke bed (ear test on **Psychosomatic**, May 2026; synthetic 30s tone not meaningful)

**Note:** WAV export uses stdlib `wave` (avoids torchaudio `torchcodec` on Windows).

**Second testable point:** core logic without Modal.

```powershell
.\.venv\Scripts\python.exe scripts\test_demucs_local.py
# Expect: scripts/output/vocals.wav, scripts/output/instrumental.wav
```

---

### Step 3 — Local CLI script + timing

| # | Action |
|---|--------|
| 3.1 | Flesh out `scripts/test_demucs_local.py` (argparse, timing, exit codes) |
| 3.2 | Document typical local runtime in this file’s docstring or PHASE_3 notes |

**Gate:**

- [x] Script completes on 30s clip (~66s CPU on reference machine; &lt;5 min)
- [x] Re-run overwrites `scripts/output/*.wav`
- [x] Clear error if fixture missing

**Third testable point:** one command from repo root.

```powershell
.\.venv\Scripts\python.exe scripts\test_demucs_local.py
.\.venv\Scripts\python.exe scripts\test_demucs_local.py --input scripts\fixtures\sample_30s.mp3
```

---

### Step 4 — Vocal fixture for Phase 4

| # | Action |
|---|--------|
| 4.1 | `python scripts/save_vocal_fixture.py` (from `scripts/output/vocals.wav`) |
| 4.2 | Or `test_demucs_local.py --save-fixture` in one command |
| 4.3 | `vocals_30s.wav` gitignored (~5 MB); regenerate locally |

**Gate:**

- [x] `vocals_30s.wav` exists (30s, 44.1 kHz WAV)
- [x] Phase 4 default: `scripts/test_whisper_local.py` → `scripts/fixtures/vocals_30s.wav`
- [x] Ear test on real song: Psychosomatic vocals/instrumental sound good (synthetic `vocals_30s` from tone fixture is not speech — use `psychosomatic/vocals.wav` for Phase 4)

**Fourth testable point:** Phase 4 input file ready (no Whisper yet).

```powershell
.\.venv\Scripts\python.exe scripts\save_vocal_fixture.py
.\.venv\Scripts\python.exe scripts\smoke_phase3_step4.py
```

---

### Step 5 — Modal `demucs_image` + GPU function

| # | Action |
|---|--------|
| 5.1 | Add `_DEMUCS_IMAGE` and `separate_stems` to `app.py` (imports `separate.py`) |
| 5.2 | Mount Volume or use ephemeral `/tmp/<job_id>/` for outputs |
| 5.3 | Upload or bake fixture into image for smoke (small clip) **or** pass bytes via Modal mount |

**Gate:**

- [x] `modal run app.py::smoke_demucs_separate` completes on T4
- [x] Separation ~5.4s on 30s clip when warm (first run includes image build + model download)
- [x] Logs print `VOCALS_PATH`, `INSTRUMENTAL_PATH`, `ELAPSED_S`

**Fifth testable point:** GPU separation without web API.

```powershell
cd backend
..\.venv\Scripts\modal.exe run app.py::smoke_demucs_separate
# Or from repo root:
.\.venv\Scripts\python.exe scripts\smoke_demucs_modal.py
```

**Image:** `_DEMUCS_IMAGE` — `ffmpeg` + `requirements-demucs.txt` + `add_local_dir(backend)` + fixture at `/fixtures/sample_30s.mp3`.

---

### Step 6 — Deployed Modal smoke

| # | Action |
|---|--------|
| 6.1 | `modal deploy app.py` (includes `separate_stems`, `smoke_demucs_separate`) |
| 6.2 | `scripts/smoke_demucs_modal.py` calls `Function.from_name("karaoke", "smoke_demucs_separate")` |

**Gate:**

- [x] Deploy succeeds; app `karaoke` on Modal (`separate_stems` + stub API unchanged)
- [x] Smoke script passes against **deployed** function (~5.5s GPU on warm container)

**Sixth testable point:** production Modal app runs Demucs smoke without `modal run`.

```powershell
cd backend
..\.venv\Scripts\modal.exe deploy app.py
cd ..
.\.venv\Scripts\python.exe scripts\smoke_demucs_modal.py
# One-shot deploy + smoke:
.\.venv\Scripts\python.exe scripts\smoke_demucs_modal.py --deploy
# Step 5 ephemeral run:
.\.venv\Scripts\python.exe scripts\smoke_demucs_modal.py --local-run
```

---

### Step 7 — Quality checklist (full song)

| # | Action |
|---|--------|
| 7.1 | `python scripts/copy_psychosomatic_fixture.py` (or pass path to your MP3) |
| 7.2 | `python scripts/smoke_phase3_step7.py` — local CPU (~5 min for 3 min song) |
| 7.3 | Optional: `smoke_phase3_step7.py --modal-only` after deploy with fixture in image |
| 7.4 | Listen to outputs; confirm vocals vs instrumental quality |

**Gate:**

- [x] Automated: stems exist, non-empty, durations match (~192s for Psychosomatic)
- [x] Local CPU: **~315s** for ~3 min song (well under 30 min)
- [x] Modal T4: `smoke_demucs_psychosomatic` on deployed app (if fixture present at deploy)
- [x] Ear test: vocal intelligible; instrumental usable as karaoke bed (user sign-off May 2026)

**Seventh testable point:** real song → `scripts/output/psychosomatic/*.wav`

```powershell
.\.venv\Scripts\python.exe scripts\copy_psychosomatic_fixture.py "C:\Users\jacob\Downloads\Psychosomatic.mp3"
.\.venv\Scripts\python.exe scripts\smoke_phase3_step7.py
# GPU only (after deploy with Psychosomatic.mp3 in fixtures/):
.\.venv\Scripts\python.exe scripts\smoke_phase3_step7.py --modal-only
```

`Psychosomatic.mp3` is **gitignored** — do not commit commercial tracks.

---

### Step 8 — Docs + README

| # | Action |
|---|--------|
| 8.1 | Mark Phase 3 progress in this file |
| 8.2 | Update root `README.md` — Demucs local + Modal commands |
| 8.3 | Update [IMPLEMENTATION_PLAN](./IMPLEMENTATION_PLAN.md) Phase 3 pointer |
| 8.4 | Commit; push `main` |

**Gate:**

- [x] [Completion checklist](#phase-3-completion-checklist) required items checked
- [x] Phase 2 production site still works (stub pipeline unchanged; `orchestrator.py` still sleep stubs)

---

## Phase 3 completion checklist

**All required boxes** must be checked before [Phase 4](./IMPLEMENTATION_PLAN.md#phase-4--transcription--alignment-in-isolation-faster-whisper--whisperx).

### Local

- [x] `scripts/fixtures/sample_30s.mp3` documented / present locally
- [x] `scripts/test_demucs_local.py` produces `vocals.wav` + `instrumental.wav`
- [x] Local run completes in acceptable time on 30s clip (~66s CPU reference)
- [x] `scripts/fixtures/vocals_30s.wav` saved for Phase 4 (`save_vocal_fixture.py`)

### Backend / Modal

- [x] `backend/separate.py` implements real Demucs (not stub)
- [x] `requirements-demucs.txt` used by **`demucs_image` only** (web image still lean)
- [x] `separate_stems` Modal function on **T4** completes on fixture
- [x] `smoke_demucs_separate` passes (`modal run`; ~5s GPU on warm container)
- [x] `smoke_demucs_modal.py` after `modal deploy` (Step 6)

### Quality

- [x] Vocal stem intelligible; instrumental reduced vocals (ear test on Psychosomatic, May 2026)
- [x] Output duration matches input (± padding) — ~192s stems from ~3 min MP3

### Explicitly NOT done (confirmed)

- [x] No changes to `orchestrator.py` pipeline logic
- [x] No faster-whisper / WhisperX in `requirements.txt` or `_BACKEND_IMAGE` / `_DEMUCS_IMAGE`
- [x] No FFmpeg render
- [x] No R2 upload of stems
- [x] No frontend upload → real separation yet

---

## Exit criteria → Phase 4

Phase 3 is **complete** when:

1. [Completion checklist](#phase-3-completion-checklist) required items are checked.
2. One **local command** and one **Modal function** both produce **vocals + instrumental** from the same fixture.
3. Vocal stem for Phase 4: `scripts/fixtures/vocals_30s.wav` (tone-derived) and/or **`scripts/output/psychosomatic/vocals.wav`** (real song; preferred for Whisper).
4. Phase 2 API and Vercel app still run the **stub** orchestrator (no regression).

**Next:** [Phase 4 — Transcription + alignment](./PHASE_4.md) — `vocals.wav` → `lyrics.json` via faster-whisper + WhisperX.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `CUDA out of memory` on Modal | Use T4; shorter clip; `htdemucs` not `htdemucs_ft` |
| Local run very slow | Expected on CPU; use 30s fixture; optional local CUDA |
| `ModuleNotFoundError: demucs` | Install `requirements-demucs.txt` in active venv |
| Modal import error for `separate` | `add_local_dir(backend)` on **`_DEMUCS_IMAGE`** (same pattern as Phase 2) |
| Huge Docker build | Split images — do not add torch to `_BACKEND_IMAGE` |
| `sample_30s.mp3` missing | Add under `scripts/fixtures/`; see fixtures README |
| Bleedy instrumental | Try `--shifts` / demucs docs; document for Phase 6; v1 accepts “good enough” |
| Web API broke after deploy | Phase 3 should not change `karaoke_api` ASGI; redeploy if accidental edit |

---

## Modal commands reference

```powershell
# Local separation
.\.venv\Scripts\python.exe scripts\test_demucs_local.py

# Modal GPU (from backend/)
cd backend
modal run app.py::smoke_demucs_separate
modal deploy app.py
modal app logs karaoke
```

**Image split reminder:**

| Image | Used by | Contains |
|-------|---------|----------|
| `_BACKEND_IMAGE` | `karaoke_api`, jobs, stub orchestrator | modal, fastapi |
| `_DEMUCS_IMAGE` | `separate_stems` | torch, demucs |

---

## Lessons learned (Phase 3 retrospective)

| Topic | Planned | What happened | Doc / process fix |
|-------|---------|---------------|-------------------|
| Modal images | Single backend image | Torch + Demucs only on **`_DEMUCS_IMAGE`**; `_BACKEND_IMAGE` stays lean | Same `add_local_dir(backend)` pattern as Phase 2; document three-image split before Phase 4 |
| WAV export | torchaudio save | `torchcodec` missing on Windows → custom **`_save_wav`** in `separate.py` | Stdlib `wave` + numpy; no torchcodec in Demucs path |
| Local runtime | “&lt;5 min” on 30s | **~66s CPU** on 30s fixture; **~315s CPU** on ~3 min Psychosomatic | Document per-clip; use GPU Modal for full songs |
| Modal GPU | T4 separation | **~5.4s** warm 30s smoke; **~12s** Psychosomatic on deployed `smoke_demucs_psychosomatic` | First `modal run` includes image build + model download |
| Fixtures | `vocals_30s` for Phase 4 | Tone-only `sample_30s` → near-silent vocal stem; **Psychosomatic** has real speech | Phase 4 smokes prefer loud vocal paths; don’t ear-test Whisper on tone fixture |
| Modal CLI (Windows) | `modal` on PATH | Often only **`.venv\Scripts\modal.exe`** | Document in commands; use `;` not `&&` in PowerShell |
| Full song in image | Optional | `Psychosomatic.mp3` baked at deploy if present under `fixtures/` (gitignored) | `copy_psychosomatic_fixture.py` + Step 7 smokes |

---

*Phase 3 runbook v2.0 — complete May 2026; Phase 4 transcription next.*
