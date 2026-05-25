import { mockCreateJob, mockGetJobStatus } from "../mocks/mockJobApi";
import type { JobStatusResponse, StartJobResponse } from "../types/job";

export function isMockMode(): boolean {
  return import.meta.env?.VITE_USE_MOCK === "true";
}

export const API_BASE =
  import.meta.env?.VITE_API_URL ?? "http://localhost:5173/api";

export async function startJob(file: File): Promise<StartJobResponse> {
  if (isMockMode()) {
    return mockCreateJob(file);
  }

  const formData = new FormData();
  formData.append("audio", file);
  const res = await fetch(`${API_BASE}/start-job`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    throw new Error(`start-job failed: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<StartJobResponse>;
}

/** Fire-and-forget GPU warm-up when user selects a file (Phase 7). */
export function warmPipeline(): void {
  if (isMockMode()) {
    return;
  }
  void fetch(`${API_BASE}/warm`, { method: "POST" }).catch(() => {
    /* ignore — upload still works on cold GPUs */
  });
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  if (isMockMode()) {
    return mockGetJobStatus(jobId);
  }

  const url = new URL(`${API_BASE}/job-status`);
  url.searchParams.set("job_id", jobId);
  const res = await fetch(url.toString());
  if (res.status === 404) {
    throw new Error("Job not found");
  }
  if (!res.ok) {
    throw new Error(`job-status failed: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<JobStatusResponse>;
}

export type { JobStatusResponse, StartJobResponse };
