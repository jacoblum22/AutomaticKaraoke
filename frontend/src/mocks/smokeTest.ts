import { getJobStatus, isMockMode, startJob } from "../api/client";
import { validateAudio, formatBytes } from "../lib/validateAudio";

const TERMINAL = new Set(["done", "failed"]);

/**
 * Dev-only smoke test. Step 3: exercises api/client.ts (not mockJobApi directly).
 */
export async function runMockSmokeTest(): Promise<boolean> {
  if (!isMockMode()) {
    console.warn("[Phase 1 smoke] VITE_USE_MOCK is not true — skipping");
    return false;
  }

  console.group("[Phase 1 smoke] validateAudio");
  const bad = new File([new ArrayBuffer(8)], "notes.txt", { type: "text/plain" });
  const badResult = validateAudio(bad);
  console.log("reject .txt:", badResult);

  const good = new File([new ArrayBuffer(2048)], "clip.mp3", { type: "audio/mpeg" });
  const goodResult = validateAudio(good);
  console.log("accept .mp3:", goodResult, formatBytes(good.size));
  console.groupEnd();

  if (!badResult.ok || !goodResult.ok) {
    console.error("[Phase 1 smoke] validateAudio FAILED");
    return false;
  }

  console.group("[Phase 1 smoke] client.startJob / getJobStatus (mock)");
  const { job_id } = await startJob(good);
  console.log("job_id:", job_id);

  let lastStatus = "";
  while (true) {
    const res = await getJobStatus(job_id);
    if (res.status !== lastStatus) {
      console.log(res.status, res.progress, res.message, res.video_url ?? "");
      lastStatus = res.status;
    }
    if (TERMINAL.has(res.status)) {
      console.groupEnd();
      const ok = res.status === "done" && res.video_url === "/sample.mp4";
      console.log(
        ok ? "[Phase 1 smoke] client API OK (no fetch)" : "[Phase 1 smoke] client API FAILED",
        res
      );
      return ok;
    }
    await new Promise((r) => setTimeout(r, 400));
  }
}
