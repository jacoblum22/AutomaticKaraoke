import { useCallback, useEffect, useState } from "react";
import {
  API_BASE,
  finalizeJob,
  getApiConfig,
  getJobStatus,
  hasClientApiKey,
  isMockMode,
  startJob,
} from "./api/client";
import { ProgressTracker } from "./components/ProgressTracker";
import { UploadForm } from "./components/UploadForm";
import { VideoPlayer } from "./components/VideoPlayer";
import { useJobPolling } from "./hooks/useJobPolling";
import type { JobStatusResponse } from "./types/job";
import "./App.css";

function App() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatusResponse | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [formKey, setFormKey] = useState(0);
  const [configWarning, setConfigWarning] = useState<string | null>(null);

  useEffect(() => {
    if (isMockMode()) return;
    void getApiConfig()
      .then((cfg) => {
        if (cfg.api_key_required && !hasClientApiKey()) {
          setConfigWarning(
            "Modal requires an API key, but this Vercel build has no VITE_API_KEY. " +
              "In Vercel: set VITE_API_KEY (not Sensitive), then redeploy with cache cleared."
          );
        } else {
          setConfigWarning(null);
        }
      })
      .catch(() => {
        /* ignore */
      });
  }, []);

  const processing =
    busy ||
    (jobId !== null &&
      jobStatus !== null &&
      jobStatus.status !== "done" &&
      jobStatus.status !== "failed");

  const handleTerminal = useCallback((res: JobStatusResponse) => {
    setBusy(false);
    if (res.status === "done" && res.video_url) {
      setVideoUrl(res.video_url);
      setJobId(null);
    }
    if (res.status === "failed") {
      setJobId(null);
    }
  }, []);

  useJobPolling(jobId, setJobStatus, handleTerminal);

  const handleFinalize = async (draftJobId: string, file?: File) => {
    setStartError(null);
    setVideoUrl(null);
    setBusy(true);
    setJobStatus({
      job_id: draftJobId,
      status: "queued",
      progress: 0,
      message: "Starting pipeline…",
    });

    const t0 = performance.now();
    try {
      const { job_id } =
        isMockMode() && file ? await startJob(file) : await finalizeJob(draftJobId);
      if (import.meta.env.DEV) {
        console.info(
          `[timing] finalize-job: ${(performance.now() - t0).toFixed(0)} ms`,
          { job_id }
        );
      }
      setJobId(job_id);
      const t1 = performance.now();
      const initial = await getJobStatus(job_id);
      if (import.meta.env.DEV) {
        console.info(
          `[timing] first job-status: ${(performance.now() - t1).toFixed(0)} ms`
        );
      }
      setJobStatus(initial);
    } catch (err) {
      setBusy(false);
      setJobStatus(null);
      setStartError(
        err instanceof Error ? err.message : "Could not start processing"
      );
    }
  };

  const handleReset = () => {
    setBusy(false);
    setJobId(null);
    setJobStatus(null);
    setVideoUrl(null);
    setStartError(null);
    setFormKey((k) => k + 1);
  };

  return (
    <main className="app">
      <header className="app__header">
        <h1>Automatic Karaoke</h1>
        <p className="app__subtitle">
          {isMockMode()
            ? "Upload a song — mock pipeline (Phase 1)"
            : "Upload a song — Demucs, Whisper, and render on Modal (GPU)"}
        </p>
      </header>

      <section className="app__panel">
        <UploadForm key={formKey} disabled={processing} onSubmit={handleFinalize} />

        {startError && (
          <p className="app__error" role="alert">
            {startError}
          </p>
        )}

        <ProgressTracker
          status={jobStatus?.status ?? null}
          progress={jobStatus?.progress}
          message={jobStatus?.message}
          error={jobStatus?.error}
          indeterminate={busy && (jobStatus?.progress ?? 0) === 0}
        />

        <VideoPlayer src={videoUrl} />

        {(videoUrl || jobStatus?.status === "failed") && (
          <button type="button" className="btn btn--secondary" onClick={handleReset}>
            Process another song
          </button>
        )}
      </section>

      {configWarning && (
        <p className="app__error app__config-warning" role="alert">
          {configWarning}
        </p>
      )}

      <footer className="app__footer">
        <p>
          Mock mode: <code>{isMockMode() ? "on" : "off"}</code>
        </p>
        {!isMockMode() && (
          <>
            <p>
              API: <code>{API_BASE}</code>
            </p>
            <p>
              Client API key: <code>{hasClientApiKey() ? "set" : "missing"}</code>
            </p>
          </>
        )}
      </footer>
    </main>
  );
}

export default App;
