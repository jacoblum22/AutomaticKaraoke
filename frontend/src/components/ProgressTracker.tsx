import { Check, Circle, Loader2 } from "lucide-react";
import type { JobStatus } from "../types/job";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";
import { Progress, ProgressLabel, ProgressValue } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

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

/** Index of the active step; ``STEPS.length`` when ``done`` (all steps checked). */
function stepIndex(status: JobStatus | null): number {
  if (!status || status === "failed") return -1;
  if (status === "done") return STEPS.length;
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
  const pct = Math.min(100, Math.max(0, progress ?? 0));
  const activeLabel =
    status === "done"
      ? "Complete"
      : (STEPS[current]?.label ?? "Processing");

  if (failed) {
    return (
      <Alert variant="destructive" className="w-full" aria-live="polite">
        <AlertTitle>Processing failed</AlertTitle>
        <AlertDescription>
          <p>{error ?? "Something went wrong while processing your track."}</p>
          <p className="mt-2 text-muted-foreground">
            Try another file or use &ldquo;Process another song&rdquo; to start
            over.
          </p>
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="flex flex-col gap-4" aria-live="polite">
      <Progress
        value={indeterminate ? null : pct}
        className="w-full"
        trackClassName="relative h-2 overflow-hidden"
        indicatorClassName={cn(
          indeterminate &&
            "w-2/5 animate-[progress-indeterminate_1.1s_ease-in-out_infinite]"
        )}
      >
        <div className="flex w-full min-w-0 basis-full items-baseline justify-between gap-2">
          <ProgressLabel className="truncate">{activeLabel}</ProgressLabel>
          {!indeterminate && <ProgressValue />}
        </div>
      </Progress>

      {message && (
        <p className="text-sm text-muted-foreground">{message}</p>
      )}

      <ol className="flex flex-col gap-2">
        {STEPS.map((step, i) => {
          const state =
            i < current
              ? "done"
              : i === current && current < STEPS.length
                ? "active"
                : "upcoming";
          return (
            <li
              key={step.status}
              className={cn(
                "flex items-center gap-3 text-sm",
                state === "active" && "font-medium text-foreground",
                state === "done" && "text-muted-foreground",
                state === "upcoming" && "text-muted-foreground/55"
              )}
            >
              <span
                className="flex size-6 shrink-0 items-center justify-center"
                aria-hidden
              >
                {state === "done" && (
                  <Check className="size-4 text-primary" strokeWidth={2.5} />
                )}
                {state === "active" && (
                  <Loader2 className="size-4 animate-spin text-primary" />
                )}
                {state === "upcoming" && (
                  <Circle className="size-2 fill-current text-border" />
                )}
              </span>
              <span>{step.label}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
