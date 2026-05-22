import type { JobStatusResponse, StartJobResponse } from "../types/job";

export const API_BASE =
  import.meta.env.VITE_API_URL ?? "http://localhost:5173/api";

// Phase 2: implement real fetch helpers
// export async function startJob(audio: File): Promise<StartJobResponse> { ... }
// export async function getJobStatus(jobId: string): Promise<JobStatusResponse> { ... }

export type { JobStatusResponse, StartJobResponse };
