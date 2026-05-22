import { useCallback, useState } from "react";
import { getJobStatus, isMockMode, startJob } from "./api/client";
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

  const processing =
    jobId !== null &&
    jobStatus !== null &&
    jobStatus.status !== "done" &&
    jobStatus.status !== "failed";

  const handleTerminal = useCallback((res: JobStatusResponse) => {
    if (res.status === "done" && res.video_url) {
      setVideoUrl(res.video_url);
      setJobId(null);
    }
    if (res.status === "failed") {
      setJobId(null);
    }
  }, []);

  useJobPolling(jobId, setJobStatus, handleTerminal);

  const handleUpload = async (file: File) => {
    setStartError(null);
    setVideoUrl(null);
    setJobStatus(null);

    try {
      const { job_id } = await startJob(file);
      setJobId(job_id);
      const initial = await getJobStatus(job_id);
      setJobStatus(initial);
    } catch (err) {
      setStartError(
        err instanceof Error ? err.message : "Could not start processing"
      );
    }
  };

  const handleReset = () => {
    setJobId(null);
    setJobStatus(null);
    setVideoUrl(null);
    setStartError(null);
  };

  return (
    <main className="app">
      <header className="app__header">
        <h1>Automatic Karaoke</h1>
        <p className="app__subtitle">
          Upload a song — mock pipeline (Phase 1)
        </p>
      </header>

      <section className="app__panel">
        <UploadForm disabled={processing} onSubmit={handleUpload} />

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
        />

        <VideoPlayer src={videoUrl} />

        {(videoUrl || jobStatus?.status === "failed") && (
          <button type="button" className="btn btn--secondary" onClick={handleReset}>
            Process another song
          </button>
        )}
      </section>

      <footer className="app__footer">
        <p>
          Mock mode: <code>{isMockMode() ? "on" : "off"}</code>
        </p>
      </footer>
    </main>
  );
}

export default App;
