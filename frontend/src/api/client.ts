/// <reference lib="dom" />
import { mockCreateJob, mockGetJobStatus } from "../mocks/mockJobApi";
import type { JobStatusResponse, StartJobResponse } from "../types/job";

/** Match backend ``GPU_SCALEDOWN_WINDOW`` (seconds). */
export const WARM_TTL_MS = 120_000;

let lastWarmAt = 0;
let cachedConfig: ApiConfig | null = null;

export type ApiConfig = {
  r2_upload: boolean;
  api_key_required: boolean;
};

export function isMockMode(): boolean {
  return import.meta.env?.VITE_USE_MOCK === "true";
}

export const API_BASE =
  import.meta.env?.VITE_API_URL ?? "http://localhost:5173/api";

function apiKey(): string {
  return (import.meta.env?.VITE_API_KEY as string | undefined)?.trim() ?? "";
}

/** True when this build has a client API key (for footer / diagnostics). */
export function hasClientApiKey(): boolean {
  return apiKey().length > 0;
}

export function apiHeaders(extra?: Record<string, string>): HeadersInit {
  const headers: Record<string, string> = { ...extra };
  const key = apiKey();
  if (key) {
    headers["X-API-Key"] = key;
  }
  return headers;
}

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

/** Server capabilities (R2 presigned upload, API key required). */
export async function getApiConfig(): Promise<ApiConfig> {
  if (isMockMode()) {
    return { r2_upload: false, api_key_required: false };
  }
  if (cachedConfig) {
    return cachedConfig;
  }
  const res = await fetch(`${API_BASE}/config`);
  if (!res.ok) {
    throw new Error(`config failed: ${res.status} ${res.statusText}`);
  }
  cachedConfig = (await res.json()) as ApiConfig;
  return cachedConfig;
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
  const res = await fetch(`${API_BASE}/draft-job`, {
    method: "POST",
    headers: apiHeaders(),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(parseErrorDetail(detail, res.statusText));
  }
  return res.json() as Promise<{ job_id: string }>;
}

export type UploadUrlResponse = {
  job_id: string;
  upload_url: string;
  object_key: string;
  content_type: string;
};

export async function getUploadUrl(
  jobId: string,
  file: File
): Promise<UploadUrlResponse> {
  const res = await fetch(`${API_BASE}/upload-url`, {
    method: "POST",
    headers: apiHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      job_id: jobId,
      filename: file.name,
      content_type: file.type || "application/octet-stream",
      size: file.size,
    }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(parseErrorDetail(detail, res.statusText));
  }
  return res.json() as Promise<UploadUrlResponse>;
}

export function uploadToPresignedUrl(
  uploadUrl: string,
  file: File,
  contentType: string,
  options?: {
    signal?: AbortSignal;
    onProgress?: (percent: number) => void;
  }
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", uploadUrl);
    xhr.setRequestHeader("Content-Type", contentType);
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
      reject(new Error(`R2 upload failed: HTTP ${xhr.status}`));
    };
    xhr.onerror = () => reject(new Error("R2 upload network error"));
    xhr.onabort = () => reject(new DOMException("Upload aborted", "AbortError"));

    if (options?.signal) {
      if (options.signal.aborted) {
        xhr.abort();
        return;
      }
      options.signal.addEventListener("abort", () => xhr.abort(), { once: true });
    }

    xhr.send(file);
  });
}

export async function syncDraftUpload(jobId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/draft-job/${jobId}/sync-upload`, {
    method: "POST",
    headers: apiHeaders(),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(parseErrorDetail(detail, res.statusText));
  }
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
    const key = apiKey();
    if (key) {
      xhr.setRequestHeader("X-API-Key", key);
    }
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

/** Presigned R2 when configured; otherwise multipart to Modal. */
export async function uploadDraftAudio(
  jobId: string,
  file: File,
  options?: {
    signal?: AbortSignal;
    onProgress?: (percent: number) => void;
  }
): Promise<void> {
  const config = await getApiConfig();
  if (!config.r2_upload) {
    return uploadDraftFile(jobId, file, options);
  }

  const { upload_url, content_type } = await getUploadUrl(jobId, file);
  await uploadToPresignedUrl(upload_url, file, content_type, options);
  await syncDraftUpload(jobId);
}

export async function deleteDraftJob(jobId: string): Promise<void> {
  if (isMockMode()) {
    return;
  }
  const res = await fetch(`${API_BASE}/draft-job/${jobId}`, {
    method: "DELETE",
    headers: apiHeaders(),
  });
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
  const res = await fetch(url.toString(), {
    method: "POST",
    headers: apiHeaders(),
  });
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
    headers: apiHeaders(),
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
