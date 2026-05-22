import type { JobStatus } from "../types/job";

const STEPS: { status: JobStatus; label: string }[] = [
  { status: "queued", label: "Queued" },
  { status: "separating", label: "Separating vocals" },
  { status: "transcribing", label: "Transcribing" },
  { status: "aligning", label: "Aligning lyrics" },
  { status: "rendering", label: "Rendering video" },
  { status: "done", label: "Complete" },
];

type Props = {
  status: JobStatus | null;
  progress?: number;
  message?: string;
  error?: string;
  /** Pulse bar at 0% while waiting for start-job (upload / cold start). */
  indeterminate?: boolean;
};

function stepIndex(status: JobStatus | null): number {
  if (!status || status === "failed") return -1;
  return STEPS.findIndex((s) => s.status === status);
}

export function ProgressTracker({
  status,
  progress,
  message,
  error,
  indeterminate = false,
}: Props) {
  if (!status) return null;

  const current = stepIndex(status);
  const failed = status === "failed";

  return (
    <div className="progress-tracker" aria-live="polite">
      {failed ? (
        <p className="progress-tracker__error" role="alert">
          {error ?? "Processing failed"}
        </p>
      ) : (
        <>
          <div className="progress-tracker__bar" aria-hidden>
            <div
              className={`progress-tracker__bar-fill${indeterminate ? " progress-tracker__bar-fill--indeterminate" : ""}`}
              style={indeterminate ? undefined : { width: `${progress ?? 0}%` }}
            />
          </div>
          {message && <p className="progress-tracker__message">{message}</p>}
          <ol className="progress-tracker__steps">
            {STEPS.map((step, i) => {
              let state = "upcoming";
              if (i < current) state = "done";
              else if (i === current) state = "active";
              return (
                <li
                  key={step.status}
                  className={`progress-tracker__step progress-tracker__step--${state}`}
                >
                  {step.label}
                </li>
              );
            })}
          </ol>
        </>
      )}
    </div>
  );
}
