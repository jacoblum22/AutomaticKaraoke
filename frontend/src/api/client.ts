/// <reference lib="dom" />
import { mockCreateJob, mockGetJobStatus } from "../mocks/mockJobApi";
import type { JobStatusResponse, StartJobResponse } from "../types/job";

/** Match backend ``GPU_SCALEDOWN_WINDOW`` (seconds). */
export const WARM_TTL_MS = 120_000;

let lastWarmAt = 0;

export function isMockMode(): boolean {
  return import.meta.env?.VITE_USE_MOCK === "true";
}

export const API_BASE =
  import.meta.env?.VITE_API_URL ?? "http://localhost:5173/api";

function parseErrorDetail(raw: string, fallback: string): string {
  if (!raw) return fallback;
  try {
    const parsed = JSON.parse(raw) as { detail?: string };
    if (typeof parsed.detail === "string") {
      return parsed.detail;
    }
  } catch {
    /* use raw body */
  }
  return raw;
}

/** POST /warm only if GPUs are likely cold (Phase 7 Step 2b). */
export function warmIfNeeded(): void {
  if (isMockMode()) {
    return;
  }
  const now = Date.now();
  if (now - lastWarmAt < WARM_TTL_MS) {
    return;
  }
  lastWarmAt = now;
  void fetch(`${API_BASE}/warm`, { method: "POST" }).catch(() => {
    /* ignore — upload still works on cold GPUs */
  });
}

export async function createDraftJob(): Promise<{ job_id: string }> {
  if (isMockMode()) {
    return { job_id: "mock-draft" };
  }
  const res = await fetch(`${API_BASE}/draft-job`, { method: "POST" });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(parseErrorDetail(detail, res.statusText));
  }
  return res.json() as Promise<{ job_id: string }>;
}

export function uploadDraftFile(
  jobId: string,
  file: File,
  options?: {
    signal?: AbortSignal;
    onProgress?: (percent: number) => void;
  }
): Promise<void> {
  if (isMockMode()) {
    options?.onProgress?.(100);
    return Promise.resolve();
  }

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/draft-job/${jobId}/upload`);
    xhr.upload.onprogress = (event: ProgressEvent) => {
      if (event.lengthComputable && options?.onProgress) {
        options.onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
        return;
      }
      reject(
        new Error(parseErrorDetail(xhr.responseText, `upload failed: ${xhr.status}`))
      );
    };
    xhr.onerror = () => reject(new Error("Upload network error"));
    xhr.onabort = () => reject(new DOMException("Upload aborted", "AbortError"));

    if (options?.signal) {
      if (options.signal.aborted) {
        xhr.abort();
        return;
      }
      options.signal.addEventListener("abort", () => xhr.abort(), { once: true });
    }

    const formData = new FormData();
    formData.append("audio", file);
    xhr.send(formData);
  });
}

export async function deleteDraftJob(jobId: string): Promise<void> {
  if (isMockMode()) {
    return;
  }
  const res = await fetch(`${API_BASE}/draft-job/${jobId}`, { method: "DELETE" });
  if (!res.ok && res.status !== 404) {
    const detail = await res.text();
    throw new Error(parseErrorDetail(detail, res.statusText));
  }
}

export async function finalizeJob(jobId: string): Promise<StartJobResponse> {
  if (isMockMode()) {
    return { job_id: jobId };
  }
  const url = new URL(`${API_BASE}/finalize-job`);
  url.searchParams.set("job_id", jobId);
  const res = await fetch(url.toString(), { method: "POST" });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(parseErrorDetail(detail, res.statusText));
  }
  return res.json() as Promise<StartJobResponse>;
}

/** Legacy one-shot path (smokes). Production UI uses draft + finalize. */
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
    const detail = await res.text();
    throw new Error(parseErrorDetail(detail, res.statusText));
  }
  return res.json() as Promise<StartJobResponse>;
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
