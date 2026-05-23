# Phase 5 — FFmpeg + ASS Render in Isolation

**Parent doc:** [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)  
**Prerequisite:** [PHASE_4.md](./PHASE_4.md) exit criteria (`lyrics.json` with word timestamps; [PHASE_3](./PHASE_3.md) `instrumental.wav`)  
**Estimated time:** 8–16 hours (FFmpeg install + ASS tuning; first full-song render is manual QA)  
**Goal:** Combine **precomputed** `lyrics.json` + **instrumental.wav** → **`karaoke.mp4`** with word-by-word karaoke highlighting (ASS burn-in). No Demucs, no Whisper, no orchestrator/frontend changes.

**Out of scope for Phase 5:** Vocal separation (Phase 3), transcription (Phase 4), R2 upload, wiring `render.py` into `orchestrator.py` / `start-job`, frontend changes.

### Current progress

| Status | Steps |
|--------|--------|
| Done | **1** FFmpeg + ffprobe on PATH — first testable point ✓ |
| Done | **2** `lyrics_to_ass` (ASS karaoke tags) — second testable point ✓ |
| Done | **3** FFmpeg burn-in → `karaoke.mp4` — third testable point ✓ |
| Done | **4** Local CLI polish + validation — fourth testable point ✓ |
| Done | **5** Full-song `psychosomatic/karaoke.mp4` — fifth testable point ✓ |
| Done | **6** Modal `_RENDER_IMAGE` + `smoke_render_fixture` — sixth testable point ✓ |
| Done | **7** Deployed render smoke + API regression — seventh testable point ✓ |
| Done | **8** Docs + sign-off — Phase 5 complete ✓ |

**Status:** Phase 5 **complete** (May 2026). Next: [Phase 6](./PHASE_6.md).

**Production API (unchanged):** https://automatic-karaoke.vercel.app — Phase 2 **stub** orchestrator until Phase 6.

**Inputs from prior phases:**

| Input | Path |
|-------|------|
| Short lyrics (30s clip) | `scripts/output/lyrics.json` (Phase 4) |
| Short instrumental | `scripts/output/instrumental.wav` (Phase 3) |
| Full-song lyrics | `scripts/output/psychosomatic/lyrics.json` (Phase 4 Step 5) |
| Full-song instrumental | `scripts/output/psychosomatic/instrumental.wav` (Phase 3 Step 7) |

**Next after Phase 5:** [Phase 6 — Integrate ML pipeline](./PHASE_6.md).

---

## Entry criteria

Before starting Phase 5:

- [ ] [Phase 4 exit](./PHASE_4.md#exit-criteria--phase-5) satisfied (`lyrics.json` validates; Psychosomatic full song recommended)
- [ ] `scripts/output/psychosomatic/instrumental.wav` + `lyrics.json` exist **or** 30s pair under `scripts/output/`
- [ ] **FFmpeg** on PATH locally (`ffmpeg -version`) — required for Steps 3+
- [ ] `modal profile current` shows `jacoblum22` (for Step 6+)
- [ ] Python venv (`.venv`) active

**Critical rule:** Render uses **`instrumental.wav` only** — never burn lyrics over the full mix or vocal stem. Karaoke bed = instrumental; vocals are already removed by Demucs.

---

## Architecture (Phase 5 — isolation only)

```text
lyrics.json     (Phase 4 — word start/end)
instrumental.wav (Phase 3 — no_vocals bed)
       ↓
┌──────────────────────────────────────┐
│  render.py                           │
│    1) lyrics → subtitles.ass ({\k})  │
│    2) FFmpeg: audio + ASS → MP4      │
└──────────────────────────────────────┘
       ↓
scripts/output/karaoke.mp4
(or scripts/output/psychosomatic/karaoke.mp4)
       ↓
Phase 6 orchestrator uploads MP4 → signed URL
```

**Not in Phase 5:**

```text
orchestrator.py real rendering stage   ← Phase 6
start-job → real MP4 URL               ← Phase 6
frontend VideoPlayer real output       ← Phase 6 (stub sample.mp4 until then)
```

| Layer | Phase 5 | Phase 6 |
|-------|---------|---------|
| `render.py` | Real ASS + FFmpeg | Called after transcribe+align |
| `transcribe.py` / `separate.py` | Unchanged | Already real |
| `orchestrator.py` | Stub sleeps | Calls render with Volume paths |
| Modal image | **`_RENDER_IMAGE`** (ffmpeg, CPU) | Separate from GPU images |

---

## Input contract (`lyrics.json`)

Consumed from [Phase 4 output contract](./PHASE_4.md#output-contract-lyricsjson). Reuse `scripts/validate_lyrics_json.py` before render.

```json
{
  "language": "en",
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

**Render assumptions (v1):**

- Word `start`/`end` are seconds (float), already aligned (WhisperX)
- One ASS dialogue line per segment; intra-line karaoke via `{\kXX}` tags
- Audio duration ≥ last word `end` (pad instrumental if shorter in v2)

---

## ASS + FFmpeg strategy (v1)

| Step | Tool | Choice |
|------|------|--------|
| Subtitle format | ASS | Karaoke `\k` centiseconds per word |
| Style | ASS `[V4+ Styles]` | Bottom-center, large outline font; primary = highlight color |
| Video | FFmpeg `lavfi` | Black 1080p canvas + instrumental audio (WAV in, MP4 out) |
| Burn-in | `-vf ass=subtitles.ass` | Escape path for Windows/colons per FFmpeg docs |
| Codec | `libx264` + `aac` | Browser-friendly H.264 / AAC |

**Example dialogue line (conceptual):**

```text
Dialogue: 0,0:00:12.34,0:00:15.67,Karaoke,{\k25}never {\k32}gonna {\k40}give ...
```

**FFmpeg command shape (implemented in `render.py`):**

```powershell
ffmpeg -y -f lavfi -i color=c=black:s=1920x1080:r=30 -i instrumental.wav ^
  -vf "ass=subtitles.ass" -map 0:v -map 1:a -c:v libx264 -c:a aac -shortest karaoke.mp4
```

Keep **`lyrics_to_ass()`** pure (JSON → `.ass` string) so you can unit-test ASS without FFmpeg.

---

## Fixtures and outputs

| Path | Source | Purpose |
|------|--------|---------|
| `scripts/output/lyrics.json` | Phase 4 | Default short render input |
| `scripts/output/instrumental.wav` | Phase 3 | Default short render input |
| `scripts/output/karaoke.mp4` | Phase 5 | Default short output (gitignored) |
| `scripts/output/psychosomatic/lyrics.json` | Phase 4 | Full-song render |
| `scripts/output/psychosomatic/instrumental.wav` | Phase 3 | Full-song render |
| `scripts/output/psychosomatic/karaoke.mp4` | Phase 5 | Full-song output (gitignored) |
| `scripts/output/subtitles.ass` | optional debug | Inspect generated ASS (gitignored) |

**Pairing rule:** Use **matching** clip lengths — 30s `lyrics.json` with 30s `instrumental.wav`, or full Psychosomatic pair. Mismatched durations cause drift or early cutoff.

---

## Target repository tree (Phase 5 changes)

```text
backend/
├── requirements.txt              # unchanged (modal + fastapi)
├── requirements-render.txt         (new) — optional thin deps; ffmpeg is system/apt
├── render.py                       (content) — lyrics_to_ass(), render_karaoke()
└── app.py                          (update) — _RENDER_IMAGE, render fn, smokes

scripts/
├── test_render_local.py            — CLI → karaoke.mp4
├── validate_ass.py                 — ASS structure smoke
├── smoke_phase5_step1.py           — ffmpeg gate
├── smoke_phase5_step2.py           — ASS generation gate
├── smoke_phase5_step3.py           — 30s render gate
├── smoke_phase5_step4.py           — CLI + validation gate
├── smoke_phase5_step5.py           — full-song render gate
├── smoke_phase5_step6.py           — Modal CPU render (modal run)
├── smoke_render_modal.py           — deployed Modal render smoke
└── fixtures/README.md              — Phase 5 inputs

docs/
└── PHASE_5.md                        (this file)
```

**Not created / not modified in Phase 5:**

| Path | Phase |
|------|-------|
| `transcribe.py` / `separate.py` | 3–4 (done) |
| `orchestrator.py` real stages | 6 |
| `frontend/` | 6 |
| R2 `storage.py` uploads | 6/7 |

---

## File minimums

### `backend/requirements-render.txt`

```text
# Phase 5 — render image / local venv (optional Python helpers only)
# FFmpeg must be on PATH (local) or apt_install (Modal image).
# No torch / demucs / whisper here.
```

v1 can be **empty** or list a small helper (e.g. nothing beyond stdlib). Do **not** add heavy ML deps to `_RENDER_IMAGE`.

### `backend/render.py`

- `RenderError` — clear failures for missing files / FFmpeg nonzero exit
- `lyrics_to_ass(lyrics: dict, *, style: AssStyle | None) -> str` — ASS v4+ header + Events
- `write_ass(path, lyrics)` — optional helper
- `render_karaoke(instrumental_path, lyrics_path, output_mp4, *, ass_path=None, resolution=(1920,1080), fps=30)` → `Path`
- `get_audio_duration(path)` — via ffprobe or wave (for sanity checks)
- No Modal imports (pure Python + subprocess)

**Karaoke timing:** For each word, `\k` duration = `(word.end - word.start) * 100` centiseconds (ASS karaoke convention). Insert spaces between words as needed.

### `backend/app.py` (additions)

```python
_RENDER_IMAGE = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg")
    .pip_install_from_requirements(.../"requirements-render.txt")  # if any
    .add_local_dir(_BACKEND_DIR, remote_path="/root")
)
# Optional at deploy: bake psychosomatic instrumental + lyrics for smokes
if _PSYCHO_LYRICS.is_file() and _PSYCHO_INSTRUMENTAL.is_file():
    _render_image = _render_image.add_local_file(...)

@app.function(image=_RENDER_IMAGE, timeout=600)  # CPU — no gpu=
def render_karaoke_modal(instrumental_path: str, lyrics_path: str, output_mp4: str) -> str:
    ...

@app.function(image=_RENDER_IMAGE, timeout=1200)
def smoke_render_fixture(*, clip_end: float | None = 30.0) -> dict:
    """Render bundled psychosomatic pair (optional clip via lyrics word filter or ffmpeg -t)."""
```

Keep **`_BACKEND_IMAGE`**, **`_DEMUCS_IMAGE`**, **`_WHISPER_IMAGE`** unchanged.

### `scripts/test_render_local.py`

- Default inputs: `scripts/output/instrumental.wav` + `scripts/output/lyrics.json`
- Default output: `scripts/output/karaoke.mp4`
- Flags: `--instrumental`, `--lyrics`, `--output`, `--ass-out`, `--resolution`, `--clip-end`
- Print elapsed time; exit non-zero on failure
- Docstring: typical CPU runtime (30s vs full song)

### `scripts/validate_ass.py` (optional Step 2 gate)

- Assert `[Script Info]`, `[V4+ Styles]`, `[Events]`, at least one `Dialogue:` line
- No FFmpeg required

---

## Step-by-step execution order

Complete in order. Each **Gate** must pass before the next step.

### Step 1 — FFmpeg available

| # | Action |
|---|--------|
| 1.1 | Install FFmpeg locally (Windows: `winget install FFmpeg` or zip on PATH) |
| 1.2 | `ffmpeg -version` and `ffprobe -version` |
| 1.3 | `scripts/smoke_phase5_step1.py` |

**Gate:**

- [x] `ffmpeg` and `ffprobe` invocable from repo venv shell (`scripts/smoke_phase5_step1.py`)
- [x] Version prints (4.x+ recommended)

**First testable point:** toolchain only.

```powershell
ffmpeg -version
.\.venv\Scripts\python.exe scripts\smoke_phase5_step1.py
```

---

### Step 2 — ASS generation (no FFmpeg)

| # | Action |
|---|--------|
| 2.1 | Implement `lyrics_to_ass()` in `render.py` |
| 2.2 | Write test ASS from `scripts/output/lyrics.json` (or psychosomatic) |
| 2.3 | Optional: `validate_ass.py` |

**Gate:**

- [x] `.ass` file contains valid `[Script Info]` + `Dialogue:` lines
- [x] Karaoke `{\k` tags present for words (`validate_ass.py`)
- [x] One Dialogue line per segment; k-tag count matches word count

**Second testable point:** subtitles file without video.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_phase5_step2.py
.\.venv\Scripts\python.exe scripts\validate_ass.py scripts\output\subtitles.ass
```

---

### Step 3 — `render.py` FFmpeg burn-in

| # | Action |
|---|--------|
| 3.1 | Implement `render_karaoke()` subprocess to FFmpeg |
| 3.2 | Handle Windows path escaping for `ass=` filter |
| 3.3 | Smoke: 30s instrumental + 30s lyrics → `karaoke.mp4` |

**Gate:**

- [x] `karaoke.mp4` exists, non-zero size
- [ ] Plays in VLC / browser; audio is instrumental bed (manual QA)
- [ ] Lyrics visible; highlight advances word-by-word (manual QA)
- [x] 30s clip: local CPU render **~10.5s** reference (psychosomatic pair, `--clip-end 30`)

**Third testable point:** local MP4 from paired inputs.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_phase5_step3.py
.\.venv\Scripts\python.exe scripts\test_render_local.py `
  --instrumental scripts\output\psychosomatic\instrumental.wav `
  --lyrics scripts\output\psychosomatic\lyrics.json `
  --output scripts\output\karaoke_30s.mp4 --clip-end 30
```

**Note:** If 30s `lyrics.json` was produced from a **30s vocal clip** but `instrumental.wav` is from the tone fixture, prefer the **psychosomatic** pair for quality QA (Step 5).

---

### Step 4 — Local CLI polish

| # | Action |
|---|--------|
| 4.1 | Complete `test_render_local.py` (argparse, errors, `--ass-out`) |
| 4.2 | Document runtime in docstring / this file |

**Gate:**

- [x] One command from repo root produces valid `karaoke.mp4`
- [x] Clear error if lyrics or instrumental missing
- [x] `validate_lyrics_json.py` runs before render (default in `test_render_local.py`)

**Fourth testable point:** same as Step 3 CLI (repeatable).

```powershell
.\.venv\Scripts\python.exe scripts\smoke_phase5_step4.py
.\.venv\Scripts\python.exe scripts\test_render_local.py
```

---

### Step 5 — Full-song render (recommended)

| # | Action |
|---|--------|
| 5.1 | Render `psychosomatic/instrumental.wav` + `psychosomatic/lyrics.json` |
| 5.2 | Output `scripts/output/psychosomatic/karaoke.mp4` |

**Gate:**

- [x] MP4 exists, non-zero size (`smoke_phase5_step5.py`)
- [ ] MP4 duration ~3 min (± a few seconds) — ffprobe in smoke; manual confirm
- [ ] Lyrics stay in sync for **chorus + verse** (ear/eye test — pause and spot-check 10 words)
- [x] No crash on long ASS (many Dialogue lines)

**Fifth testable point:** real song karaoke file.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_phase5_step5.py
.\.venv\Scripts\python.exe scripts\test_render_local.py `
  --instrumental scripts\output\psychosomatic\instrumental.wav `
  --lyrics scripts\output\psychosomatic\lyrics.json `
  --output scripts\output\psychosomatic\karaoke.mp4 --no-clip
```

---

### Step 6 — Modal `_RENDER_IMAGE` + CPU function

| # | Action |
|---|--------|
| 6.1 | Add `_RENDER_IMAGE` + `render_karaoke_modal` to `app.py` |
| 6.2 | Bake psychosomatic `instrumental.wav` + `lyrics.json` at deploy (if present) |
| 6.3 | `smoke_render_fixture` — 30s or full song |

**Gate:**

- [x] `modal run app.py::smoke_render_fixture` completes (CPU container)
- [x] Returns MP4 path + elapsed; file non-empty
- [ ] Warm run **&lt;90s** for 30s clip; full song **&lt;3 min** acceptable (check logs)

**Sixth testable point:** FFmpeg render on Modal without web API.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_phase5_step6.py
cd backend
..\.venv\Scripts\modal.exe run app.py::smoke_render_fixture
```

---

### Step 7 — Deployed Modal smoke

| # | Action |
|---|--------|
| 7.1 | `modal deploy app.py` |
| 7.2 | `scripts/smoke_render_modal.py` → `Function.from_name("karaoke", "smoke_render_fixture").remote()` |

**Gate:**

- [x] Deploy lists `render_karaoke_modal` + `smoke_render_fixture`
- [x] Smoke passes on **deployed** app
- [x] `karaoke-api` still serves stub jobs (`smoke_modal_deployed.py`)

```powershell
.\.venv\Scripts\python.exe scripts\smoke_render_modal.py --deploy
.\.venv\Scripts\python.exe scripts\smoke_render_modal.py
.\.venv\Scripts\python.exe scripts\smoke_render_modal.py --skip-api
```

---

### Step 8 — Docs + Phase 5 sign-off

| # | Action |
|---|--------|
| 8.1 | Mark progress in this file |
| 8.2 | Update root `README.md` + [IMPLEMENTATION_PLAN](./IMPLEMENTATION_PLAN.md) |
| 8.3 | Check [completion checklist](#phase-5-completion-checklist) |
| 8.4 | Commit + push `main` when ready |

**Gate:**

- [x] Required checklist items checked
- [x] Phases 2–4 production paths unchanged (stub orchestrator; `smoke_render_modal.py` runs API regression)

**Eighth testable point:** documentation and sign-off (this section).

---

## Phase 5 completion checklist

**All required boxes** must be checked before [Phase 6](./PHASE_6.md).

### Local

- [x] FFmpeg on PATH; `smoke_phase5_step1.py` passes
- [x] `render.py` implements `lyrics_to_ass` + `render_karaoke`
- [x] `test_render_local.py` → valid `karaoke.mp4` (30s pair minimum)
- [x] `validate_lyrics_json.py` passes on input JSON before render (default in CLI)

### Quality

- [x] ASS karaoke highlight advances word-by-word (basic style OK for v1)
- [x] MP4 plays in browser and VLC (manual QA on `psychosomatic/karaoke.mp4`)
- [x] Sync spot-check: 10 words vs instrumental (±0.15s acceptable v1; user sign-off)
- [x] Full-song `psychosomatic/karaoke.mp4` eye-test (~194s, 5.6 MB)

### Backend / Modal

- [x] `_RENDER_IMAGE` separate from `_BACKEND_IMAGE` / `_DEMUCS_IMAGE` / `_WHISPER_IMAGE`
- [x] `smoke_render_fixture` on CPU completes (`smoke_phase5_step6.py`, ~4s warm / 30s clip)
- [x] `smoke_render_modal.py` after deploy (~3.6s warm / 30s clip + API regression)

### Explicitly NOT done (confirm)

- [x] No orchestrator render stage wired
- [x] No R2 upload of MP4
- [x] No frontend changes (still stub `sample.mp4` URL)
- [x] No Demucs / Whisper in render image

---

## Exit criteria → Phase 6

Phase 5 is **complete** when:

1. [Completion checklist](#phase-5-completion-checklist) required items are checked.
2. `test_render_local.py` reliably produces **`karaoke.mp4`** from validated `lyrics.json` + `instrumental.wav`.
3. Optional but recommended: **`psychosomatic/karaoke.mp4`** for demo quality.
4. Modal CPU render smoke passes on deployed app; stub API unchanged.

**Next:** [Phase 6 — Integrate ML pipeline](./PHASE_6.md).

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ffmpeg not found` | Install FFmpeg; restart shell; Step 1 smoke |
| `ass filter` path error (Windows) | Use escaped path in `render.py` (`subtitles='C\\:/path/file.ass'` or temp copy) |
| Lyrics out of sync | Confirm lyrics + instrumental from **same** Demucs run; re-run Phase 4 on same vocal stem |
| No lyrics on screen | Check ASS encoding UTF-8; verify Dialogue times match audio duration |
| Black video only | Expected (lavfi color source); audio should still play |
| FFmpeg slow on full song | Normal on CPU; use Modal `smoke_render_fixture` or lower resolution (720p) for dev |
| OOM / timeout Modal | Increase `timeout=` on render function; clip to 30s for smokes |
| Wrong words displayed | Phase 4 ASR issue — fix transcription, not render |
| `validate_lyrics` fails | Re-run Phase 4; do not render invalid JSON |

---

## Modal commands reference

```powershell
# Local
.\.venv\Scripts\python.exe scripts\test_render_local.py
.\.venv\Scripts\python.exe scripts\validate_lyrics_json.py scripts\output\psychosomatic\lyrics.json

# Phase 5 smokes (repo root)
.\.venv\Scripts\python.exe scripts\smoke_phase5_step1.py
.\.venv\Scripts\python.exe scripts\smoke_phase5_step5.py
.\.venv\Scripts\python.exe scripts\smoke_render_modal.py --deploy

# Modal CPU render (from backend/)
cd backend
..\.venv\Scripts\modal.exe run app.py::smoke_render_fixture
..\.venv\Scripts\modal.exe deploy app.py
modal app logs karaoke
```

**Image split (after Phase 5):**

| Image | Used by | Contains |
|-------|---------|----------|
| `_BACKEND_IMAGE` | `karaoke_api`, jobs, stub orchestrator | modal, fastapi |
| `_DEMUCS_IMAGE` | `separate_stems`, Demucs smokes | torch, demucs |
| `_WHISPER_IMAGE` | `transcribe_vocals_modal`, whisper smokes | faster-whisper, whisperx |
| `_RENDER_IMAGE` | `render_karaoke_modal`, render smokes | ffmpeg, `render.py` |

---

## Reference snippet (from IMPLEMENTATION_PLAN)

```python
# lyrics.json + instrumental.wav → karaoke.mp4
from render import lyrics_to_ass, render_karaoke
from pathlib import Path
import json

lyrics = json.loads(Path("scripts/output/psychosomatic/lyrics.json").read_text())
ass_text = lyrics_to_ass(lyrics)
Path("scripts/output/subtitles.ass").write_text(ass_text, encoding="utf-8")

render_karaoke(
    "scripts/output/psychosomatic/instrumental.wav",
    "scripts/output/psychosomatic/lyrics.json",
    "scripts/output/psychosomatic/karaoke.mp4",
)
```

See [§ Karaoke subtitle strategy](./IMPLEMENTATION_PLAN.md#7-karaoke-subtitle-strategy-ffmpeg--ass) in the parent plan.

---

## Lessons learned (Phase 5 retrospective)

| Topic | Planned | What happened | Doc / process fix |
|-------|---------|---------------|-------------------|
| Render inputs | Instrumental + `lyrics.json` only | Full mix / stem remix not used for burn-in; correct pairing matters for sync | Keep Phase 3+4 pair together per song |
| ASS + FFmpeg | `{\k}` centiseconds, Windows path escape | `subtitles='C\:/...'` filter works; local 30s ~10–13s, full song ~30–55s CPU | `smoke_phase5_step3`–`5` as gates |
| Modal render | CPU `_RENDER_IMAGE` | Warm 30s clip ~4s; deploy smoke ~3.6s; no GPU needed | Separate image from Demucs/Whisper |
| Transcription vs render | Wrong words in MP4 | Lyrics text is Phase 4 ASR; render only burns JSON | Do not tune FFmpeg for lyric accuracy |
| VAD (Phase 4 cross-over) | `vad_filter=True` default | `vad_filter=False` on vocal stem — more segments, same wrong ASR on hard songs | `DEFAULT_VAD_FILTER = False` in `transcribe.py` |

---

*Phase 5 runbook v1.1 — complete May 2026; integration in Phase 6.*
