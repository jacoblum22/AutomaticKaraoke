import { Clapperboard, Download, ExternalLink, Loader2 } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Props = {
  src: string | null;
  /** True while pipeline is running and no video yet. */
  processing?: boolean;
};

function downloadFilename(src: string): string {
  try {
    const path = new URL(src, window.location.origin).pathname;
    const base = path.split("/").pop();
    if (base?.includes(".")) return base;
  } catch {
    /* relative URL */
  }
  return "karaoke-video.mp4";
}

export function VideoPlayer({ src, processing = false }: Props) {
  return (
    <Card
      className="gap-0 border-border/80 bg-muted/15 py-0 shadow-none ring-0"
      aria-label="Karaoke video preview"
    >
      <CardHeader className="border-b border-border/60 pb-3">
        <CardTitle>Karaoke video</CardTitle>
        <CardDescription>
          {src
            ? "Sing along with your generated track."
            : processing
              ? "Rendering in progress…"
              : "Upload a song to generate your video."}
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-4 pt-4">
        {!src ? (
          <div
            className={cn(
              "flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border/80 px-4 py-10 text-center",
              processing ? "bg-muted/25" : "bg-muted/10"
            )}
          >
            <div
              className={cn(
                "flex size-14 items-center justify-center rounded-full",
                processing ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
              )}
            >
              {processing ? (
                <Loader2 className="size-7 animate-spin" aria-hidden />
              ) : (
                <Clapperboard className="size-7" aria-hidden />
              )}
            </div>
            <p className="max-w-xs text-sm text-muted-foreground">
              {processing
                ? "Your karaoke video will appear here when processing finishes."
                : "Drop a track above to start — lyrics and video show up here when ready."}
            </p>
          </div>
        ) : (
          <>
            <div className="overflow-hidden rounded-lg border border-border/80 bg-black">
              <video
                className="mx-auto block max-h-[min(360px,50vh)] w-full"
                controls
                src={src}
                playsInline
                preload="metadata"
              >
                <track kind="captions" />
              </video>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row">
              <a
                href={src}
                download={downloadFilename(src)}
                className={cn(buttonVariants({ variant: "default" }), "gap-1.5")}
              >
                <Download className="size-4" aria-hidden />
                Download MP4
              </a>
              <a
                href={src}
                target="_blank"
                rel="noopener noreferrer"
                className={cn(buttonVariants({ variant: "outline" }), "gap-1.5")}
              >
                <ExternalLink className="size-4" aria-hidden />
                Open in new tab
              </a>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
