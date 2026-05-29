import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type MouseEvent,
} from "react";
import { Loader2, Music, Upload, X } from "lucide-react";
import {
  createDraftJob,
  deleteDraftJob,
  isMockMode,
  uploadDraftAudio,
  warmIfNeeded,
} from "../api/client";
import {
  formatBytes,
  formatMaxDurationError,
  MAX_AUDIO_DURATION_S,
  probeAudioDuration,
  validateAudio,
} from "../lib/validateAudio";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Progress,
  ProgressLabel,
  ProgressValue,
} from "@/components/ui/progress";
import { cn } from "@/lib/utils";

type Props = {
  disabled?: boolean;
  /** Called with draft ``job_id`` when upload is complete and user submits. */
  onSubmit: (jobId: string, file?: File) => void;
};

export function UploadForm({ disabled = false, onSubmit }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const uploadAbortRef = useRef<AbortController | null>(null);
  const draftJobIdRef = useRef<string | null>(null);
  const selectGenerationRef = useRef(0);

  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<File | null>(null);
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [uploadReady, setUploadReady] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [checkingDuration, setCheckingDuration] = useState(false);

  const cancelDraftUpload = useCallback(async () => {
    uploadAbortRef.current?.abort();
    uploadAbortRef.current = null;
    const oldId = draftJobIdRef.current;
    draftJobIdRef.current = null;
    if (oldId) {
      try {
        await deleteDraftJob(oldId);
      } catch {
        /* best-effort discard */
      }
    }
  }, []);

  useEffect(() => {
    return () => {
      void cancelDraftUpload();
    };
  }, [cancelDraftUpload]);

  const clearSelection = useCallback(async () => {
    selectGenerationRef.current += 1;
    await cancelDraftUpload();
    setSelected(null);
    setUploadReady(false);
    setUploadPct(null);
    setError(null);
    setCheckingDuration(false);
    setDragOver(false);
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }, [cancelDraftUpload]);

  const startDraftUpload = useCallback(
    async (file: File) => {
      const generation = ++selectGenerationRef.current;
      await cancelDraftUpload();

      setUploadReady(false);
      setUploadPct(0);
      setUploading(true);
      setError(null);

      warmIfNeeded();

      try {
        const { job_id } = await createDraftJob();
        if (generation !== selectGenerationRef.current) {
          await deleteDraftJob(job_id);
          return;
        }

        draftJobIdRef.current = job_id;
        const abort = new AbortController();
        uploadAbortRef.current = abort;

        await uploadDraftAudio(job_id, file, {
          signal: abort.signal,
          onProgress: (pct) => {
            if (generation === selectGenerationRef.current) {
              setUploadPct(pct);
            }
          },
        });

        if (generation !== selectGenerationRef.current) {
          return;
        }

        setUploadPct(100);
        setUploadReady(true);
      } catch (err) {
        if (generation !== selectGenerationRef.current) {
          return;
        }
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        setError(err instanceof Error ? err.message : "Upload failed");
        setUploadReady(false);
      } finally {
        if (generation === selectGenerationRef.current) {
          setUploading(false);
        }
      }
    },
    [cancelDraftUpload]
  );

  const handleFile = useCallback(
    async (file: File | undefined) => {
      if (!file) return;
      const generation = ++selectGenerationRef.current;

      const result = validateAudio(file);
      if (!result.ok) {
        await cancelDraftUpload();
        setError(result.error);
        setSelected(null);
        setUploadReady(false);
        setUploadPct(null);
        setCheckingDuration(false);
        return;
      }

      await cancelDraftUpload();
      setError(null);
      setSelected(null);
      setUploadReady(false);
      setUploadPct(null);
      setCheckingDuration(true);

      if (!isMockMode()) {
        const durationS = await probeAudioDuration(file);
        if (generation !== selectGenerationRef.current) {
          return;
        }
        if (durationS !== null && durationS > MAX_AUDIO_DURATION_S) {
          setError(formatMaxDurationError(durationS));
          setCheckingDuration(false);
          return;
        }
      }

      if (generation !== selectGenerationRef.current) {
        return;
      }

      setCheckingDuration(false);
      setSelected(file);
      if (isMockMode()) {
        setUploadReady(true);
        setUploadPct(100);
        return;
      }
      void startDraftUpload(file);
    },
    [cancelDraftUpload, startDraftUpload]
  );

  const onInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    void handleFile(e.target.files?.[0]);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (disabled) return;
    void handleFile(e.dataTransfer.files[0]);
  };

  const onSubmitClick = () => {
    if (!selected || !uploadReady || uploading || checkingDuration || disabled) {
      return;
    }
    if (isMockMode()) {
      onSubmit("mock", selected);
      return;
    }
    const jobId = draftJobIdRef.current;
    if (!jobId) return;
    onSubmit(jobId);
  };

  const busy = disabled || checkingDuration || uploading;
  const submitLabel = disabled
    ? "Working…"
    : checkingDuration
      ? "Checking length…"
      : uploading
        ? "Uploading…"
        : uploadReady
          ? "Create karaoke video"
          : "Waiting for upload…";

  return (
    <div className="flex flex-col gap-4">
      {!selected ? (
        <div
          className={cn(
            "relative flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-8 text-center transition-colors",
            "border-border bg-muted/30 hover:border-primary/50 hover:bg-muted/50",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
            dragOver && "border-primary bg-primary/5",
            disabled && "pointer-events-none opacity-50"
          )}
          onDragOver={(e) => {
            e.preventDefault();
            if (!disabled) setDragOver(true);
          }}
          onDragLeave={(e) => {
            if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
              setDragOver(false);
            }
          }}
          onDrop={onDrop}
          onClick={() => !disabled && inputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              if (!disabled) inputRef.current?.click();
            }
          }}
          role="button"
          tabIndex={disabled ? -1 : 0}
          aria-disabled={disabled}
          aria-label="Upload audio file"
        >
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Upload className="h-6 w-6" aria-hidden />
          </div>
          <div>
            <p className="text-base font-medium text-foreground">
              Drop a song here or click to browse
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              MP3, WAV, M4A, FLAC, OGG — max 50 MB, 8 minutes
            </p>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept="audio/*,.mp3,.wav,.m4a,.flac,.ogg"
            hidden
            disabled={disabled}
            onChange={onInputChange}
          />
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3 rounded-lg border border-border bg-card px-3 py-2.5">
            <Music className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />
            <div className="min-w-0 flex-1 text-left">
              <p className="truncate text-sm font-medium text-foreground">
                {selected.name}
              </p>
              <p className="text-xs text-muted-foreground">
                {formatBytes(selected.size)}
              </p>
            </div>
            {uploadReady && !uploading && (
              <Badge variant="default">Ready</Badge>
            )}
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              className="shrink-0"
              disabled={disabled || busy}
              aria-label="Remove file"
              onClick={(e: MouseEvent<HTMLButtonElement>) => {
                e.stopPropagation();
                void clearSelection();
              }}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          {uploading && uploadPct !== null && (
            <Progress value={uploadPct} className="w-full">
              <ProgressLabel>Uploading</ProgressLabel>
              <ProgressValue />
            </Progress>
          )}
        </div>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Button
        type="button"
        size="lg"
        className="h-11 w-full gap-2 text-base"
        disabled={
          disabled ||
          checkingDuration ||
          !selected ||
          !uploadReady ||
          uploading ||
          !!error
        }
        onClick={onSubmitClick}
      >
        {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
        {submitLabel}
      </Button>
    </div>
  );
}
