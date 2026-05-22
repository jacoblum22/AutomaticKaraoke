export type JobStatus =
  | "queued"
  | "separating"
  | "transcribing"
  | "aligning"
  | "rendering"
  | "done"
  | "failed";

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  progress?: number;
  message?: string;
  video_url?: string;
  error?: string;
}

export interface StartJobResponse {
  job_id: string;
}
