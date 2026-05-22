const MAX_BYTES = 50 * 1024 * 1024;

const ALLOWED_MIME = new Set([
  "audio/mpeg",
  "audio/wav",
  "audio/x-wav",
  "audio/mp4",
  "audio/x-m4a",
  "audio/flac",
  "audio/ogg",
  "audio/webm",
]);

const EXTENSION_TO_MIME: Record<string, string> = {
  ".mp3": "audio/mpeg",
  ".wav": "audio/wav",
  ".m4a": "audio/mp4",
  ".mp4": "audio/mp4",
  ".flac": "audio/flac",
  ".ogg": "audio/ogg",
  ".webm": "audio/webm",
};

export type ValidateAudioResult =
  | { ok: true }
  | { ok: false; error: string };

function extensionOf(name: string): string {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i).toLowerCase() : "";
}

function isAudioType(file: File): boolean {
  if (file.type && ALLOWED_MIME.has(file.type)) return true;
  const extMime = EXTENSION_TO_MIME[extensionOf(file.name)];
  return extMime !== undefined && ALLOWED_MIME.has(extMime);
}

export function validateAudio(file: File): ValidateAudioResult {
  if (file.size > MAX_BYTES) {
    return {
      ok: false,
      error: `File is too large (${formatBytes(file.size)}). Maximum size is 50 MB.`,
    };
  }

  if (file.size === 0) {
    return { ok: false, error: "File is empty." };
  }

  if (!isAudioType(file)) {
    return {
      ok: false,
      error: `Unsupported file type. Use a common audio format (MP3, WAV, M4A, FLAC, OGG).`,
    };
  }

  return { ok: true };
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
