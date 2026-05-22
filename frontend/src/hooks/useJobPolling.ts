import { useEffect, useRef } from "react";
import { getJobStatus } from "../api/client";
import type { JobStatus, JobStatusResponse } from "../types/job";

const TERMINAL: JobStatus[] = ["done", "failed"];
const POLL_MS = 2000;

export function useJobPolling(
  jobId: string | null,
  onUpdate: (status: JobStatusResponse) => void,
  onTerminal?: (status: JobStatusResponse) => void
): void {
  const onUpdateRef = useRef(onUpdate);
  const onTerminalRef = useRef(onTerminal);

  useEffect(() => {
    onUpdateRef.current = onUpdate;
    onTerminalRef.current = onTerminal;
  }, [onUpdate, onTerminal]);

  useEffect(() => {
    if (!jobId) return;

    let cancelled = false;

    const poll = async () => {
      if (cancelled) return;
      try {
        const res = await getJobStatus(jobId);
        if (cancelled) return;
        onUpdateRef.current(res);
        if (TERMINAL.includes(res.status)) {
          onTerminalRef.current?.(res);
        }
      } catch (err) {
        if (cancelled) return;
        onUpdateRef.current({
          job_id: jobId,
          status: "failed",
          error: err instanceof Error ? err.message : "Failed to fetch job status",
          message: "Something went wrong",
        });
        onTerminalRef.current?.({
          job_id: jobId,
          status: "failed",
          error: err instanceof Error ? err.message : "Failed to fetch job status",
        });
      }
    };

    void poll();
    const intervalId = window.setInterval(() => void poll(), POLL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [jobId]);
}
