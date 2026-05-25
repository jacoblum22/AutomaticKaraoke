import {
  useCallback,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from "react";
import { warmPipeline } from "../api/client";
import { formatBytes, validateAudio } from "../lib/validateAudio";

type Props = {
  disabled?: boolean;
  onSubmit: (file: File) => void;
};

export function UploadForm({ disabled = false, onSubmit }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<File | null>(null);

  const handleFile = useCallback(
    (file: File | undefined) => {
      if (!file) return;
      const result = validateAudio(file);
      if (!result.ok) {
        setError(result.error);
        setSelected(null);
        return;
      }
      setError(null);
      setSelected(file);
      warmPipeline();
    },
    []
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
    if (!selected || disabled) return;
    onSubmit(selected);
  };

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
        <p className="dropzone__hint">MP3, WAV, M4A, FLAC, OGG — max 50 MB</p>
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
        disabled={disabled || !selected || !!error}
        onClick={onSubmitClick}
      >
        {disabled ? "Working…" : "Create karaoke video"}
      </button>
    </div>
  );
}
