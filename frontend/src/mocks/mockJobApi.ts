import type { JobStatus, JobStatusResponse, StartJobResponse } from "../types/job";

export const MOCK_VIDEO_URL = "/sample.mp4";

const STAGES: { status: JobStatus; message: string; progress: number }[] = [
  { status: "queued", message: "Queued…", progress: 0 },
  { status: "separating", message: "Separating vocals…", progress: 20 },
  { status: "transcribing", message: "Transcribing vocals…", progress: 40 },
  { status: "aligning", message: "Aligning lyrics…", progress: 60 },
  { status: "rendering", message: "Rendering karaoke video…", progress: 80 },
  { status: "done", message: "Complete!", progress: 100 },
];

const STAGE_MS = 1500;

interface JobState {
  job_id: string;
  stageIndex: number;
  fileName: string;
  fail: boolean;
  failedReady: boolean;
  timers: ReturnType<typeof setTimeout>[];
}

const jobs = new Map<string, JobState>();

function newJobId(): string {
  return crypto.randomUUID();
}

function scheduleStages(job: JobState): void {
  for (let i = 1; i < STAGES.length; i++) {
    const timer = setTimeout(() => {
      job.stageIndex = i;
      if (STAGES[i].status === "done") {
        job.timers.forEach(clearTimeout);
        job.timers.length = 0;
      }
    }, STAGE_MS * i);
    job.timers.push(timer);
  }
}

function responseFromJob(job: JobState): JobStatusResponse {
  if (job.fail && job.failedReady) {
    return {
      job_id: job.job_id,
      status: "failed",
      progress: 0,
      message: "Processing failed",
      error: "Mock failure (dev simulation).",
    };
  }

  const stage = STAGES[job.stageIndex] ?? STAGES[0];
  const res: JobStatusResponse = {
    job_id: job.job_id,
    status: stage.status,
    progress: stage.progress,
    message: stage.message,
  };

  if (stage.status === "done") {
    res.video_url = MOCK_VIDEO_URL;
  }

  return res;
}

/** Start a mock job. Does not upload file bytes anywhere. */
export async function mockCreateJob(
  file: File,
  options?: { fail?: boolean }
): Promise<StartJobResponse> {
  const job_id = newJobId();
  const job: JobState = {
    job_id,
    stageIndex: 0,
    fileName: file.name,
    fail: options?.fail ?? false,
    failedReady: false,
    timers: [],
  };
  jobs.set(job_id, job);
  if (!job.fail) {
    scheduleStages(job);
  } else {
    const timer = setTimeout(() => {
      job.failedReady = true;
    }, 500);
    job.timers.push(timer);
  }
  return { job_id };
}

export async function mockGetJobStatus(
  jobId: string
): Promise<JobStatusResponse> {
  const job = jobs.get(jobId);
  if (!job) {
    return {
      job_id: jobId,
      status: "failed",
      error: "Unknown job ID",
      message: "Job not found",
    };
  }
  return responseFromJob(job);
}

/** Remove finished jobs from memory (optional cleanup). */
export function mockClearJob(jobId: string): void {
  const job = jobs.get(jobId);
  if (job) {
    job.timers.forEach(clearTimeout);
    jobs.delete(jobId);
  }
}
