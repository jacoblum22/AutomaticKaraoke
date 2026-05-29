import { cn } from "@/lib/utils";

export type SongMetadata = {
  title: string;
  artist: string;
};

type Props = {
  value: SongMetadata;
  onChange: (value: SongMetadata) => void;
  disabled?: boolean;
};

const fieldClass =
  "mt-1.5 flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground shadow-xs outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50";

export function SongMetadataFields({ value, onChange, disabled }: Props) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="block text-left">
        <span className="text-sm font-medium text-foreground">
          Song title{" "}
          <span className="font-normal text-muted-foreground">(optional)</span>
        </span>
        <input
          type="text"
          className={cn(fieldClass)}
          placeholder="e.g. Psychosomatic"
          value={value.title}
          disabled={disabled}
          autoComplete="off"
          onChange={(e) => onChange({ ...value, title: e.target.value })}
        />
      </label>
      <label className="block text-left">
        <span className="text-sm font-medium text-foreground">
          Artist{" "}
          <span className="font-normal text-muted-foreground">(optional)</span>
        </span>
        <input
          type="text"
          className={cn(fieldClass)}
          placeholder="e.g. The Weeknd"
          value={value.artist}
          disabled={disabled}
          autoComplete="off"
          onChange={(e) => onChange({ ...value, artist: e.target.value })}
        />
      </label>
      <p className="text-xs text-muted-foreground sm:col-span-2">
        Not sent to the server yet — for future lyric lookup.
      </p>
    </div>
  );
}
