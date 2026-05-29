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
import { cn } from "./lib/utils";
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
    <div className="relative flex min-h-svh flex-col font-sans text-foreground">
      <div
        className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgb(192_132_252/18%),transparent)]"
        aria-hidden
      />
      <div
        className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_100%_100%,rgb(99_102_241/8%),transparent_40%)]"
        aria-hidden
      />

      <header className="relative px-4 pb-2 pt-8 text-center sm:px-6 sm:pt-12 lg:px-8">
        <p className="mb-2 text-xs font-medium uppercase tracking-widest text-accent">
          Automatic Karaoke
        </p>
        <h1 className="font-display text-3xl font-semibold tracking-tight text-heading sm:text-4xl lg:text-5xl">
          Turn any song into karaoke
        </h1>
        <p className="mx-auto mt-3 max-w-md text-sm text-muted sm:text-base">
          {isMockMode()
            ? "Local mock pipeline — upload a track to preview the UI flow."
            : "Upload audio — we separate vocals, transcribe lyrics, and render a sing-along video on Modal GPU."}
        </p>
      </header>

      <main className="relative mx-auto w-full max-w-lg flex-1 px-4 pb-10 sm:px-6 lg:max-w-xl lg:px-8">
        {configWarning && (
          <p
            className="mb-4 rounded-xl border border-destructive/30 bg-destructive-muted px-4 py-3 text-sm text-destructive"
            role="alert"
          >
            {configWarning}
          </p>
        )}

        <section
          className={cn(
            "flex flex-col gap-6 rounded-2xl border border-border bg-card/90 p-5 shadow-2xl shadow-black/20 backdrop-blur-sm",
            "sm:p-7 lg:p-8"
          )}
          aria-label="Upload and processing"
        >
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
      </main>

      <footer className="relative border-t border-border/60 px-4 py-6 text-center text-xs text-muted sm:px-6">
        {import.meta.env.DEV ? (
          <div className="mx-auto flex max-w-lg flex-col gap-1">
            <p>
              Mock mode: <code>{isMockMode() ? "on" : "off"}</code>
            </p>
            {!isMockMode() && (
              <>
                <p>
                  API: <code>{API_BASE}</code>
                </p>
                <p>
                  Client API key:{" "}
                  <code>{hasClientApiKey() ? "set" : "missing"}</code>
                </p>
              </>
            )}
          </div>
        ) : (
          <p>GPU processing on Modal · Hosted on Vercel</p>
        )}
      </footer>
    </div>
  );
}

export default App;
