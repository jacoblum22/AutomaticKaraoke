"""Modal app entrypoint. Phase 2: web endpoints; Phase 6: orchestration."""

import modal

app = modal.App("karaoke")

# Phase 2: @app.function + @modal.web_endpoint for POST /start-job, GET /job-status
# Phase 6: orchestrator calling separate → transcribe → render
