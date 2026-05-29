import { Badge } from "@/components/ui/badge";
import { API_BASE, hasClientApiKey, isMockMode } from "../api/client";

export function DevDebugFooter() {
  if (!import.meta.env.DEV) {
    return (
      <p>GPU processing on Modal · Hosted on Vercel</p>
    );
  }

  return (
    <details className="mx-auto max-w-lg text-left">
      <summary className="cursor-pointer list-none text-center marker:content-none [&::-webkit-details-marker]:hidden">
        <span className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground">
          Debug
          <Badge variant="secondary" className="font-mono text-[0.65rem]">
            dev
          </Badge>
        </span>
      </summary>
      <div className="mt-3 space-y-1 rounded-lg border border-border/60 bg-muted/20 px-3 py-2 text-left font-mono text-[0.7rem] leading-relaxed">
        <p>
          Mock: <code>{isMockMode() ? "on" : "off"}</code>
        </p>
        {!isMockMode() && (
          <>
            <p className="break-all">
              API: <code>{API_BASE}</code>
            </p>
            <p>
              API key:{" "}
              <code>{hasClientApiKey() ? "configured" : "missing"}</code>
            </p>
          </>
        )}
      </div>
    </details>
  );
}
