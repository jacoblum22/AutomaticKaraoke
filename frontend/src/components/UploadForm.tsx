import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from "react";
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
    handleFile(e.target.files?.[0]);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (disabled) return;
    handleFile(e.dataTransfer.files[0]);
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
    <div className="upload-form">
      <div
        className={`dropzone${dragOver ? " dropzone--active" : ""}${disabled ? " dropzone--disabled" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
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
        <p className="dropzone__title">Drop a song here or click to browse</p>
        <p className="dropzone__hint">
          MP3, WAV, M4A, FLAC, OGG — max 50 MB, 8 minutes
        </p>
        <input
          ref={inputRef}
          type="file"
          accept="audio/*,.mp3,.wav,.m4a,.flac,.ogg"
          hidden
          disabled={disabled}
          onChange={onInputChange}
        />
      </div>

      {selected && !error && (
        <p className="upload-form__file">
          <strong>{selected.name}</strong> ({formatBytes(selected.size)})
          {uploadPct !== null && uploading && (
            <> — uploading {uploadPct}%</>
          )}
          {uploadReady && !uploading && <> — ready</>}
        </p>
      )}

      {error && (
        <p className="upload-form__error" role="alert">
          {error}
        </p>
      )}

      <button
        type="button"
        className="btn btn--primary"
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
        {submitLabel}
      </button>
    </div>
  );
}
