# Local isolation scripts

Run from the **repository root**:

```bash
# Phase 4 Step 1 — whisper deps + vocal fixture
pip install -r backend/requirements-whisper.txt
python scripts/smoke_phase4_step1.py
python scripts/smoke_phase4_step2.py

# Phase 4 Step 3 — transcribe + align → lyrics.json (~3 min CPU on 30s clip)
python scripts/test_whisper_local.py --clip-end 30
python scripts/validate_lyrics_json.py scripts/output/lyrics.json
python scripts/smoke_phase4_step3.py

# Phase 4 Step 6–7 — Modal GPU Whisper (bakes psychosomatic/vocals.wav at deploy)
cd backend
..\.venv\Scripts\modal.exe run app.py::smoke_whisper_fixture
..\.venv\Scripts\modal.exe deploy app.py
cd ..
python scripts/smoke_whisper_modal.py
python scripts/smoke_whisper_modal.py --deploy

# Phase 4 Step 5 — full-song lyrics.json (Modal GPU)
python scripts/smoke_phase4_step5.py
python scripts/smoke_phase4_step5.py --local

# Phase 5 Step 1 — FFmpeg on PATH (install separately; not a pip package)
.\.venv\Scripts\python.exe scripts\smoke_phase5_step1.py
.\.venv\Scripts\python.exe scripts\smoke_phase5_step2.py
.\.venv\Scripts\python.exe scripts\smoke_phase5_step3.py
.\.venv\Scripts\python.exe scripts\smoke_phase5_step4.py
.\.venv\Scripts\python.exe scripts\smoke_phase5_step5.py
.\.venv\Scripts\python.exe scripts\smoke_phase5_step6.py
.\.venv\Scripts\python.exe scripts\smoke_render_modal.py --deploy
.\.venv\Scripts\python.exe scripts\test_render_local.py --clip-end 30
.\.venv\Scripts\python.exe scripts\test_render_local.py --no-clip `
  --output scripts\output\psychosomatic\karaoke.mp4

# Phase 3 Step 1 — fixture + demucs/torch in venv
python scripts/generate_sample_fixture.py
pip install -r backend/requirements-demucs.txt
python scripts/smoke_phase3_step1.py

# Phase 3 Step 2–3 — local Demucs (CPU ~1–5 min on 30s clip; first run downloads model)
python scripts/test_demucs_local.py
python scripts/save_vocal_fixture.py
python scripts/smoke_phase3_step4.py

# Phase 3 Step 5 — Modal GPU Demucs (builds demucs image first time ~3 min)
cd backend
..\.venv\Scripts\modal.exe run app.py::smoke_demucs_separate

# Phase 3 Step 6 — deployed app smoke
cd backend && ..\.venv\Scripts\modal.exe deploy app.py && cd ..
python scripts/smoke_demucs_modal.py

# Phase 3 Step 7 — full song (Psychosomatic.mp3, gitignored; ~5 min CPU / ~12s GPU)
python scripts/copy_psychosomatic_fixture.py
python scripts/smoke_phase3_step7.py
python scripts/smoke_phase3_step7.py --modal-only

# Phase 2 — Modal job store (requires modal CLI + auth)
python scripts/smoke_jobs_dict.py

# Phase 2 — stub orchestrator (spawn + poll; ~20–40s typical)
python scripts/smoke_orchestrator.py

# Phase 2 — HTTP API (modal serve; first run rebuilds image ~30–60s)
python scripts/smoke_modal_api.py --serve

# Phase 2 — HTTP API (deployed production URL; run after `modal deploy` in backend/)
python scripts/smoke_modal_deployed.py

# Phase 2 — frontend client.ts against Modal (from frontend/)
# cd frontend && npm run smoke:modal
# cd frontend && npm run measure:start-job   # start-job latency vs file size

# Phase 2 — Dict persistence + 404 (many polls; optional mid-job redeploy)
python scripts/smoke_job_durability.py
python scripts/smoke_job_durability.py --redeploy-mid

python scripts/test_demucs_local.py
python scripts/test_whisper_local.py
```

- **`fixtures/`** — add `sample_30s.mp3` in Phase 3 (short clip; avoid committing copyrighted full tracks).
- **`output/`** — generated WAV, JSON, and MP4 artifacts (gitignored).
