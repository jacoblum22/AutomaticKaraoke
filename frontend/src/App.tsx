import { useCallback, useEffect, useState } from "react";
import {
  finalizeJob,
  getApiConfig,
  getJobStatus,
  hasClientApiKey,
  isMockMode,
  startJob,
} from "./api/client";
import { DevDebugFooter } from "./components/DevDebugFooter";
import { ProgressTracker } from "./components/ProgressTracker";
import {
  SongMetadataFields,
  type SongMetadata,
} from "./components/SongMetadataFields";
import { UploadForm } from "./components/UploadForm";
import { VideoPlayer } from "./components/VideoPlayer";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
  const [songMeta, setSongMeta] = useState<SongMetadata>({
    title: "",
    artist: "",
  });

  useEffect(() => {
    if (isMockMode()) return;
    void getApiConfig()
      .then((cfg) => {
        if (cfg.api_key_required && !hasClientApiKey()) {
          setConfigWarning(
            "Modal requires an API key, but VITE_API_KEY is missing in this dev build. " +
              "Add it to frontend/.env.local (same value as Modal secret karaoke-api-key) and restart npm run dev."
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
      setJobStatus(null);
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
    setSongMeta({ title: "", artist: "" });
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
        <p className="mx-auto mt-3 max-w-md text-sm text-muted-foreground sm:text-base">
          {isMockMode()
            ? "Local mock pipeline — upload a track to preview the UI flow."
            : "Upload audio — we separate vocals, transcribe lyrics, and render a sing-along video on Modal GPU."}
        </p>
      </header>

      <main className="relative mx-auto w-full max-w-lg flex-1 px-4 pb-10 sm:px-6 lg:max-w-xl lg:px-8">
        {configWarning && (
          <Alert variant="destructive" className="mb-4">
            <AlertTitle>API key required</AlertTitle>
            <AlertDescription>{configWarning}</AlertDescription>
          </Alert>
        )}

        <Card
          className="border-border/80 bg-card/95 shadow-2xl shadow-black/25 backdrop-blur-sm"
          aria-label="Upload and processing"
        >
          <CardContent className="flex flex-col gap-6 pt-6 sm:pt-6">
            <SongMetadataFields
              value={songMeta}
              onChange={setSongMeta}
              disabled={processing}
            />
            <UploadForm key={formKey} disabled={processing} onSubmit={handleFinalize} />

            {startError && (
              <Alert variant="destructive">
                <AlertDescription>{startError}</AlertDescription>
              </Alert>
            )}

            <ProgressTracker
              status={jobStatus?.status ?? null}
              progress={jobStatus?.progress}
              message={jobStatus?.message}
              error={jobStatus?.error}
              indeterminate={busy && (jobStatus?.progress ?? 0) === 0}
            />

            <VideoPlayer
              src={videoUrl}
              processing={processing && !videoUrl}
            />

            {(videoUrl || jobStatus?.status === "failed") && (
              <Button
                type="button"
                variant="outline"
                className="w-full"
                onClick={handleReset}
              >
                Process another song
              </Button>
            )}
          </CardContent>
        </Card>
      </main>

      <footer className="relative border-t border-border/60 px-4 py-6 text-center text-xs text-muted-foreground sm:px-6">
        <DevDebugFooter />
      </footer>
    </div>
  );
}

export default App;
