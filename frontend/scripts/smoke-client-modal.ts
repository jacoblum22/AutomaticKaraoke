/**
 * Phase 2 Step 5 gate — client.ts against deployed Modal API (vite-node + .env.modal).
 */
import { validateAudio } from "../src/lib/validateAudio";
import { API_BASE, getJobStatus, isMockMode, startJob } from "../src/api/client";

const STUB_VIDEO = "https://automatic-karaoke.vercel.app/sample.mp4";
const POLL_MS = 2000;
const TIMEOUT_MS = 60_000;

const good = new File([new Uint8Array(100)], "a.mp3", { type: "audio/mpeg" });
if (!validateAudio(good).ok) {
  console.error("validateAudio FAIL");
  process.exit(1);
}

if (isMockMode()) {
  console.error("VITE_USE_MOCK must be false (use .env.modal or .env.local)");
  process.exit(1);
}

console.log("API_BASE:", API_BASE);
console.log("mock mode:", isMockMode());

const t0 = Date.now();
const { job_id } = await startJob(good);
console.log("start-job:", job_id, `(${(Date.now() - t0) / 1000}s)`);

let last = "";
const deadline = Date.now() + TIMEOUT_MS;
while (Date.now() < deadline) {
  const s = await getJobStatus(job_id);
  if (s.status !== last) {
    console.log(s.status, s.progress ?? "", s.message ?? "");
    last = s.status;
  }
  if (s.status === "done") {
    if (s.video_url !== STUB_VIDEO) {
      console.error("unexpected video_url:", s.video_url);
      process.exit(1);
    }
    console.log("client API OK (Modal)", s.video_url);
    process.exit(0);
  }
  if (s.status === "failed") {
    console.error("job failed:", s.error);
    process.exit(1);
  }
  await new Promise((r) => setTimeout(r, POLL_MS));
}
console.error("poll timeout");
process.exit(1);
