# Local isolation scripts

Run from the **repository root**:

```bash
# Phase 4 Step 1 — whisper deps + vocal fixture
python scripts/smoke_phase4_step1.py
pip install -r backend/requirements-whisper.txt

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
