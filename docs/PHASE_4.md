# Phase 4 — Transcription + Alignment in Isolation

**Parent doc:** [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)  
**Prerequisite:** [PHASE_3.md](./PHASE_3.md) exit criteria (vocals stem available; quality ear-test recommended)  
**Estimated time:** 10–20 hours (GPU helps; first Whisper/WhisperX downloads are large)  
**Goal:** From an **isolated vocal stem** (`vocals.wav`), produce **`lyrics.json`** with word-level `start` / `end` via **faster-whisper** then **WhisperX** alignment. No FFmpeg, no full-pipeline integration, no frontend changes.

**Out of scope for Phase 4:** Demucs (Phase 3), FFmpeg render (Phase 5), orchestrator wiring (Phase 6), R2, browser/UI changes.

### Current progress

| Status | Steps |
|--------|--------|
| Done | **1** whisper deps + vocal fixture — first testable point ✓ |
| Done | **2** `transcribe_vocals` (faster-whisper only) — second testable point ✓ |
| Done | **3** WhisperX align + `lyrics.json` — third testable point ✓ |
| Done | **4** local CLI polish (`test_whisper_local.py`) ✓ |
| Done | **5** full-song `psychosomatic/lyrics.json` (Modal GPU) ✓ |
| Done | **6–7** Modal `_WHISPER_IMAGE` + deployed GPU smoke — sixth/seventh testable point ✓ |
| Done | **8** docs + sign-off — **Phase 4 complete** ✓ |

**Production API (unchanged):** https://automatic-karaoke.vercel.app — Phase 2 **stub** orchestrator until Phase 6.

**Inputs from Phase 3:**

| Input | Path |
|-------|------|
| Short vocal fixture | `scripts/fixtures/vocals_30s.wav` (`save_vocal_fixture.py` after 30s Demucs) |
| Full-song vocals | `scripts/output/psychosomatic/vocals.wav` (after `smoke_phase3_step7.py`) |

**Next after Phase 4:** [Phase 5 — FFmpeg + ASS render](./IMPLEMENTATION_PLAN.md#phase-5--ffmpeg--ass-render-in-isolation) — `lyrics.json` + `instrumental.wav` → MP4.

---

## Entry criteria

Before starting Phase 4:

- [x] [Phase 3 exit](./PHASE_3.md#exit-criteria--phase-4) satisfied (stems + smokes; Psychosomatic ear-test May 2026)
- [ ] `scripts/fixtures/vocals_30s.wav` exists **or** you will use another `vocals.wav` from Phase 3 output
- [ ] `modal profile current` shows `jacoblum22` (for Step 6+)
- [ ] Python venv (`.venv`) active
- [ ] Disk space for Whisper + WhisperX + wav2vec2 models (**several GB** first download)
- [ ] Optional: local NVIDIA GPU (CPU + `int8` works but slow on 3 min vocals)

**Critical rule:** Run transcription on **`vocals.wav` only** — never the original full mix. Misaligned karaoke is often caused by skipping Demucs or transcribing the wrong stem.

---

## Architecture (Phase 4 — isolation only)

```text
vocals.wav  (from Phase 3 Demucs)
       ↓
┌─────────────────────────────────────────┐
│  transcribe.py                          │
│    1) faster-whisper — text + rough words │
│    2) WhisperX align — refine word times  │
└─────────────────────────────────────────┘
       ↓
scripts/output/lyrics.json   (or per-run subdir)
       ↓
Phase 5 render.py reads JSON + instrumental.wav
```

**Not in Phase 4:**

```text
orchestrator.py real transcribing stage   ← Phase 6
start-job / job-status progress           ← Phase 6 (stub sleeps until then)
```

| Layer | Phase 4 | Phase 6 |
|-------|---------|---------|
| `transcribe.py` | Real faster-whisper + WhisperX | Called from orchestrator after `separate` |
| `separate.py` | Unchanged | Already real (Phase 3) |
| `orchestrator.py` | Stub sleeps | Updates `transcribing` / `aligning` with real work |
| Modal image | **`whisper_image`** (separate from demucs + web) | Same split |

---

## Output contract (`lyrics.json`)

Contract for Phase 5 `render.py`. Store at `scripts/output/lyrics.json` or `scripts/output/<name>/lyrics.json`.

```json
{
  "segments": [
    {
      "start": 12.34,
      "end": 15.67,
      "text": "never gonna give you up",
      "words": [
        { "word": "never", "start": 12.34, "end": 12.58 },
        { "word": "gonna", "start": 12.58, "end": 12.90 }
      ]
    }
  ]
}
```

**Validation rules (automate in smoke):**

- `segments` is a non-empty array (unless truly silent vocal)
- Each segment has `start` &lt; `end`, `text` non-empty
- Each `words[]` entry has `word`, `start`, `end`; times monotonic within segment
- Word times should lie within segment bounds (± small tolerance)

Optional metadata (v1): top-level `"language": "en"` if detected.

---

## Model settings (recommended)

| Step | Library | Setting | Notes |
|------|---------|---------|--------|
| Transcribe | `faster-whisper` | `medium` | Upgrade to `large-v3` if lyrics wrong |
| Transcribe | | `word_timestamps=True`, `vad_filter=True` | On **vocals.wav** path |
| Transcribe | | `device=cuda`, `compute_type=float16` | Modal T4 |
| Transcribe | | `device=cpu`, `compute_type=int8` | Local without GPU |
| Align | `whisperx` | wav2vec2 align model | Same vocal stem + transcript |
| Language | | `language_code="en"` | Adjust if you add multi-lang later |

**Known limitation:** Sung lyrics, dense rap, and heavy production still cause mis-hears; WhisperX improves **timing**, not magic transcription. Manual lyric editor = v2.

---

## Fixtures and inputs

| Path | Source | Purpose |
|------|--------|---------|
| `scripts/fixtures/vocals_30s.wav` | Phase 3 `save_vocal_fixture.py` | Default short CLI input |
| `scripts/output/psychosomatic/vocals.wav` | Phase 3 Step 7 | Full-song quality test |
| `scripts/output/lyrics.json` | Phase 4 output | Default local output (gitignored) |
| `scripts/output/lyrics_30s.json` | optional | Keep separate from full-song run |

Do **not** commit large generated JSON or copyrighted vocal stems unless you have rights and repo size is acceptable.

---

## Target repository tree (Phase 4 changes)

```text
backend/
├── requirements.txt                 # unchanged (modal + fastapi)
├── requirements-whisper.txt         (new) — faster-whisper, whisperx, deps
├── transcribe.py                    (content) — transcribe_vocals(), align, to JSON
└── app.py                           (update) — WHISPER_IMAGE, transcribe fn, smokes

scripts/
├── test_whisper_local.py            (content) — CLI → lyrics.json
├── validate_lyrics_json.py          (new) — schema / monotonic smoke
├── smoke_phase4_step1.py              (new) — import deps gate
└── smoke_whisper_modal.py           (new) — deployed Modal transcribe smoke

docs/
└── PHASE_4.md                         (this file)
```

**Not created / not modified in Phase 4:**

| Path | Phase |
|------|-------|
| `render.py` logic | 5 |
| `orchestrator.py` real stages | 6 |
| `frontend/` | 6 |
| `separate.py` | 3 (done) |

---

## File minimums

### `backend/requirements-whisper.txt`

```text
faster-whisper>=1.0.0
whisperx>=3.1.0
# torch often pulled by whisperx; pin if version conflicts with demucs venv
```

Install in **separate venv** or same `.venv` as Phase 3 if versions compatible — if Demucs + Whisper fight over torch, use documented pins or separate venv (note in lessons learned).

### `backend/transcribe.py`

- `transcribe_vocals(vocals_path: Path, *, model_size="medium", device=None, language="en")` → raw segments for WhisperX
- `align_lyrics(vocals_path, segments, *, device=None)` → aligned structure
- `transcribe_and_align(vocals_path: Path, output_json: Path, **opts)` → writes contract JSON
- No Modal imports (pure Python for local + Modal image)

### `backend/app.py` (additions)

```python
_WHISPER_IMAGE = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg")  # whisperx.load_audio
    .pip_install_from_requirements(.../"requirements-whisper.txt")
    .add_local_dir(_BACKEND_DIR, remote_path="/root")
    .add_local_file(vocals_30s.wav, remote_path="/fixtures/vocals_30s.wav")  # if present
)

@app.function(image=_WHISPER_IMAGE, gpu="T4", timeout=600)
def transcribe_vocals_modal(input_path: str, output_json: str) -> str:
    ...

@app.function(image=_WHISPER_IMAGE, gpu="T4", timeout=1200)
def smoke_whisper_fixture() -> dict:
    """Run on /fixtures/vocals_30s.wav; return path + elapsed."""
```

Keep **`_BACKEND_IMAGE`** and **`_DEMUCS_IMAGE`** unchanged (no whisper deps on API image).

### `scripts/test_whisper_local.py`

- Default input: `scripts/fixtures/vocals_30s.wav`
- Default output: `scripts/output/lyrics.json`
- Flags: `--input`, `--output`, `--model`, `--device`, `--language`
- Print elapsed time; exit non-zero on failure

### `scripts/validate_lyrics_json.py`

- Load JSON; assert schema + monotonic word times
- Usable as Step 4 gate after local transcribe

---

## Step-by-step execution order

Complete in order. Each **Gate** must pass before the next step.

### Step 1 — Dependencies + import smoke

| # | Action |
|---|--------|
| 1.1 | Create `backend/requirements-whisper.txt` |
| 1.2 | `pip install -r backend/requirements-whisper.txt` in `.venv` |
| 1.3 | Verify imports (`faster_whisper`, `whisperx`) |

**Gate:**

- [x] `from faster_whisper import WhisperModel; import whisperx` succeeds in `.venv`
- [x] `vocals_30s.wav` exists (`scripts/smoke_phase4_step1.py`)

**Note:** `whisperx` upgrades torch to **2.8.x** in the shared venv. Re-run `pip install -r backend/requirements-demucs.txt` if Demucs regresses.

**First testable point:** environment only.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_phase4_step1.py
```

---

### Step 2 — `transcribe.py` (faster-whisper only)

| # | Action |
|---|--------|
| 2.1 | Implement faster-whisper path on `vocals_30s.wav` |
| 2.2 | Log segment count + first/last word times (debug) |

**Gate:**

- [x] Returns non-empty segments with word timestamps on 30s vocal fixture
- [x] Runs in acceptable time locally (CPU `int8` OK for 30s)

**Second testable point:** transcription without alignment yet.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_phase4_step2.py
```

**Fixture note:** `fixtures/vocals_30s.wav` copied from the **440 Hz tone** sample is effectively silent after Demucs (~peak 0.01). Whisper needs **real sung/spoken** vocals — the smoke uses `scripts/output/psychosomatic/vocals.wav` when present (clips first 30s on long files). Re-copy a real 30s vocal stem into `fixtures/vocals_30s.wav` for faster repeat runs.

Or from `backend/`:

```powershell
cd backend
..\.venv\Scripts\python.exe -c "from pathlib import Path; from transcribe import transcribe_vocals, log_transcription_summary; p=Path('../scripts/fixtures/vocals_30s.wav'); s=transcribe_vocals(p); log_transcription_summary(s)"
```

---

### Step 3 — WhisperX alignment + `lyrics.json`

| # | Action |
|---|--------|
| 3.1 | Add `align_lyrics` + `transcribe_and_align` in `transcribe.py` |
| 3.2 | Map WhisperX output → [output contract](#output-contract-lyricsjson) |
| 3.3 | Write `scripts/output/lyrics.json` |

**Gate:**

- [x] `lyrics.json` passes `validate_lyrics_json.py`
- [x] Word times monotonic; segments non-empty for vocal fixture (Psychosomatic 0–30s clip)

**Third testable point:** full local chain on 30s vocals.

```powershell
.\.venv\Scripts\python.exe scripts\test_whisper_local.py
.\.venv\Scripts\python.exe scripts\validate_lyrics_json.py scripts\output\lyrics.json
# Or one-shot:
.\.venv\Scripts\python.exe scripts\smoke_phase4_step3.py
```

**Reference runtime (CPU, 30s clip):** transcribe+align **~163s** after align model download (~360 MB wav2vec2).

---

### Step 4 — Local CLI polish + timing

| # | Action |
|---|--------|
| 4.1 | Complete `test_whisper_local.py` (argparse, timing, errors) |
| 4.2 | Document typical runtime in docstring (30s vs 3 min vocal) |

**Gate:**

- [x] One command from repo root produces valid `lyrics.json`
- [x] Clear error if no speech-capable vocal stem
- [x] 30s vocal: local CPU ~163s; Modal T4 ~37s warm

**Fourth testable point:** same as Step 3 CLI (repeatable).

```powershell
.\.venv\Scripts\python.exe scripts\test_whisper_local.py
.\.venv\Scripts\python.exe scripts\test_whisper_local.py --input scripts\fixtures\vocals_30s.wav
```

---

### Step 5 — Full-song vocal stem (optional, recommended)

| # | Action |
|---|--------|
| 5.1 | Run on `scripts/output/psychosomatic/vocals.wav` (Phase 3 Step 7) |
| 5.2 | Output e.g. `scripts/output/psychosomatic/lyrics.json` |

**Gate:**

- [x] JSON validates; span ends ~**187s** (39 segments, 342 words)
- [ ] Spot-check **10 words** against `vocals.wav` in a player (±0.1s on pop vocals) — manual
- [x] Produced via Modal GPU (`smoke_whisper_fixture(clip_end=None)`)

**Fifth testable point:** real song lyrics file.

```powershell
# Modal GPU (recommended, ~36s warm):
.\.venv\Scripts\python.exe scripts\smoke_phase4_step5.py

# Local CPU (slow):
.\.venv\Scripts\python.exe scripts\smoke_phase4_step5.py --local
.\.venv\Scripts\python.exe scripts\test_whisper_local.py `
  --input scripts\output\psychosomatic\vocals.wav `
  --output scripts\output\psychosomatic\lyrics.json --no-clip
```

**Reference runtime:** Modal T4 full song **~36s** warm; local CPU expect 15–30+ min.

---

### Step 6 — Modal `whisper_image` + GPU function

| # | Action |
|---|--------|
| 6.1 | Add `_WHISPER_IMAGE` + `transcribe_vocals_modal` / `smoke_whisper_fixture` to `app.py` |
| 6.2 | Bake `vocals_30s.wav` into image when present at deploy |
| 6.3 | `modal run app.py::smoke_whisper_fixture` |

**Gate:**

- [x] GPU smoke completes on 30s vocal fixture (`/fixtures/vocals_smoke.wav` = psychosomatic vocals at deploy)
- [x] Returns `lyrics` dict + metadata; validates with `validate_lyrics_json`
- [x] Warm deployed run **~37s** on T4 for 30s clip (first run includes image build + model download)

**Sixth testable point:** GPU transcribe without web API.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_phase4_step6.py
# Or:
cd backend
..\.venv\Scripts\modal.exe run app.py::smoke_whisper_fixture
```

---

### Step 7 — Deployed Modal smoke

| # | Action |
|---|--------|
| 7.1 | `modal deploy app.py` |
| 7.2 | `scripts/smoke_whisper_modal.py` → `Function.from_name("karaoke", "smoke_whisper_fixture").remote()` |

**Gate:**

- [x] Deploy succeeds; `transcribe_vocals_modal` + `smoke_whisper_fixture` listed
- [x] Smoke passes on **deployed** app (`smoke_whisper_modal.py`)
- [x] Phase 2 `karaoke-api` URL unchanged (stub pipeline)

```powershell
.\.venv\Scripts\python.exe scripts\smoke_whisper_modal.py --deploy
# Deploy only:
cd backend; ..\.venv\Scripts\modal.exe deploy app.py
# Smoke deployed (after deploy with psychosomatic/vocals.wav present):
.\.venv\Scripts\python.exe scripts\smoke_whisper_modal.py
```

---

### Step 8 — Docs + Phase 4 sign-off

| # | Action |
|---|--------|
| 8.1 | Mark progress in this file |
| 8.2 | Update `README.md` + [IMPLEMENTATION_PLAN](./IMPLEMENTATION_PLAN.md) |
| 8.3 | Check [completion checklist](#phase-4-completion-checklist) |
| 8.4 | Commit + push `main` when ready |

**Gate:**

- [x] All required checklist items checked
- [x] Phase 3 + Phase 2 production unchanged (stub orchestrator; `karaoke-api` redeployed with whisper fns only)

---

## Phase 4 completion checklist

**All required boxes** must be checked before [Phase 5](./IMPLEMENTATION_PLAN.md#phase-5--ffmpeg--ass-render-in-isolation).

### Local

- [x] `requirements-whisper.txt` installed; imports work (`smoke_phase4_step1.py`)
- [x] `transcribe.py` implements faster-whisper + WhisperX
- [x] `test_whisper_local.py` → valid `lyrics.json` (psychosomatic vocal stem; tone `vocals_30s` has no speech)
- [x] `validate_lyrics_json.py` passes on output

### Quality (30s + optional full song)

- [x] JSON schema valid (`scripts/output/lyrics.json`, `psychosomatic/lyrics.json`)
- [x] Word times monotonic within segments (automated validator)
- [ ] Spot-check 10 words vs **vocals.wav** in a player (±0.1s) — optional manual before Phase 6
- [x] WhisperX alignment run after faster-whisper (Step 3+ chain; tighter word boundaries)

### Backend / Modal

- [x] `_WHISPER_IMAGE` separate from `_BACKEND_IMAGE` / `_DEMUCS_IMAGE`
- [x] `smoke_whisper_fixture` on T4 (30s clip ~37s; full song ~36s warm)
- [x] `smoke_whisper_modal.py` after deploy

### Explicitly NOT done (confirmed)

- [x] No `render.py` / FFmpeg MP4 yet
- [x] No orchestrator transcribe stage wired
- [x] No frontend changes
- [x] No transcription on full mix (only `vocals.wav`)

---

## Exit criteria → Phase 5

Phase 4 is **complete** when:

1. [Completion checklist](#phase-4-completion-checklist) required items are checked.
2. `lyrics.json` is produced reliably from **`vocals_30s.wav`** locally and via Modal GPU.
3. Optional: `psychosomatic/lyrics.json` from full-song vocal stem validates.
4. Phase 2/3 production paths still work (stub API + Demucs unchanged).

**Next:** [Phase 5 — FFmpeg + ASS render](./IMPLEMENTATION_PLAN.md#phase-5--ffmpeg--ass-render-in-isolation) — `lyrics.json` + `instrumental.wav` → `karaoke.mp4`.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Empty `segments` | Check input is **vocals** stem; try `vad_filter=True`; verify Demucs quality |
| CUDA OOM on Modal | Shorter clip; `medium` not `large-v3`; T4 not CPU |
| torch version conflict with Demucs | Pin torch in both requirements files or split venvs |
| WhisperX align fails | Match `language_code` to audio; check segment shape for WhisperX API version |
| Drift vs audio | Re-run alignment; confirm WhisperX ran on same `vocals.wav` as whisper |
| Very slow local CPU | Use 30s fixture first; `int8`; or Modal GPU only |
| `HF_TOKEN` errors | Set Modal secret if using gated models |
| Import error in Modal | `add_local_dir(backend)` on **`_WHISPER_IMAGE`** |

---

## Modal commands reference

```powershell
# Local
.\.venv\Scripts\python.exe scripts\test_whisper_local.py
.\.venv\Scripts\python.exe scripts\validate_lyrics_json.py scripts\output\lyrics.json

# Modal (from backend/)
cd backend
..\.venv\Scripts\modal.exe run app.py::smoke_whisper_fixture
..\.venv\Scripts\modal.exe deploy app.py
modal app logs karaoke
```

**Image split (after Phase 4):**

| Image | Used by | Contains |
|-------|---------|----------|
| `_BACKEND_IMAGE` | `karaoke_api`, jobs, stub orchestrator | modal, fastapi |
| `_DEMUCS_IMAGE` | `separate_stems`, Demucs smokes | torch, demucs |
| `_WHISPER_IMAGE` | `transcribe_vocals_modal`, whisper smokes | faster-whisper, whisperx |

---

## Reference snippet (from IMPLEMENTATION_PLAN)

```python
# Input: vocals.wav (from Demucs), not the original mix
from faster_whisper import WhisperModel
import whisperx

model = WhisperModel("medium", device="cuda", compute_type="float16")
segments, _ = model.transcribe("vocals.wav", word_timestamps=True, vad_filter=True)

audio = whisperx.load_audio("vocals.wav")
align_model, metadata = whisperx.load_align_model(language_code="en", device="cuda")
result = whisperx.align(segments, align_model, metadata, audio, device="cuda")
# Map result → lyrics.json contract
```

See [Appendix A](./IMPLEMENTATION_PLAN.md#appendix-a--example-transcribe--align-isolation-snippet) in the parent plan.

---

## Lessons learned (Phase 4 retrospective)

| Topic | Planned | What happened | Doc / process fix |
|-------|---------|---------------|-------------------|
| Vocal fixture | `vocals_30s.wav` default | Tone-only Demucs stem is silent → Whisper returns 0 segments | Use `psychosomatic/vocals.wav` or real song clip; smokes pick loud stems |
| torch in venv | Shared with Demucs | `whisperx` pins torch **2.8**; Demucs still worked after install | Note in `requirements-whisper.txt`; reinstall demucs reqs if separation breaks |
| Local runtime | GPU optional | 30s clip CPU **~163s**; full song would be 15–30+ min on CPU | Default long runs to **Modal T4** (~37s for 30s and ~3 min warm) |
| Modal images | Third image | `_WHISPER_IMAGE` + bake `psychosomatic/vocals.wav` at deploy | Redeploy when vocal stem changes; same `add_local_dir(backend)` pattern |
| Alignment | WhisperX on stem | wav2vec2 download ~360 MB first local run; align bundled in chain | `validate_lyrics_json.py` for contract; return `lyrics` dict from Modal smokes |
| Full song | Local optional | Step 5 via `smoke_phase4_step5.py` + GPU; 39 segments, span **~187s** | `--no-clip` for local; `clip_end=None` on Modal |

---

*Phase 4 runbook v2.0 — complete May 2026; Phase 5 FFmpeg render next.*
