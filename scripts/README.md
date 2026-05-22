# Local isolation scripts

Run from the **repository root**:

```bash
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

# Phase 2 — Dict persistence + 404 (many polls; optional mid-job redeploy)
python scripts/smoke_job_durability.py
python scripts/smoke_job_durability.py --redeploy-mid

python scripts/test_demucs_local.py
python scripts/test_whisper_local.py
```

- **`fixtures/`** — add `sample_30s.mp3` in Phase 3 (short clip; avoid committing copyrighted full tracks).
- **`output/`** — generated WAV, JSON, and MP4 artifacts (gitignored).
