/**
 * Phase 6 Step 8 — client.ts against deployed Modal API (real pipeline + R2 URL).
 *
 * Uses Psychosomatic.mp3 from scripts/fixtures/ (same as smoke_pipeline_modal.py).
 */
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { validateAudio } from "../src/lib/validateAudio";
import { API_BASE, getJobStatus, isMockMode, startJob } from "../src/api/client";

const STUB_VIDEO = "https://automatic-karaoke.vercel.app/sample.mp4";
const POLL_MS = 3000;
const TIMEOUT_MS = 1_800_000;

const here = fileURLToPath(new URL(".", import.meta.url));
const repoRoot = resolve(here, "../..");
const fixturePath = resolve(repoRoot, "scripts/fixtures/Psychosomatic.mp3");

if (!existsSync(fixturePath)) {
  console.error("Missing fixture:", fixturePath);
  console.error("Run scripts/copy_psychosomatic_fixture.py or add Psychosomatic.mp3.");
  process.exit(1);
}

const audioBytes = readFileSync(fixturePath);
const audioFile = new File([audioBytes], "Psychosomatic.mp3", {
  type: "audio/mpeg",
});

if (!validateAudio(audioFile).ok) {
  console.error("validateAudio FAIL");
  process.exit(1);
}

if (isMockMode()) {
  console.error("VITE_USE_MOCK must be false (use .env.modal or .env.local)");
  process.exit(1);
}

function assertRealVideoUrl(videoUrl: string, jobId: string): void {
  if (!videoUrl) {
    console.error("done without video_url");
    process.exit(1);
  }
  if (videoUrl === STUB_VIDEO || videoUrl.includes("sample.mp4")) {
    console.error("video_url is still stub:", videoUrl);
    process.exit(1);
  }
  if (!videoUrl.startsWith("https://")) {
    console.error("video_url must be HTTPS:", videoUrl);
    process.exit(1);
  }
  if (!videoUrl.includes(jobId) || !videoUrl.includes("/karaoke/")) {
    console.error("unexpected video_url shape:", videoUrl);
    process.exit(1);
  }
}

console.log("fixture:", fixturePath, `(${audioBytes.length} bytes)`);
console.log("API_BASE:", API_BASE);
console.log("mock mode:", isMockMode());

const t0 = Date.now();
const { job_id } = await startJob(audioFile);
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
    const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
    assertRealVideoUrl(s.video_url ?? "", job_id);
    console.log(`wall time: ${elapsed}s`);
    console.log("video_url:", s.video_url);
    console.log("Phase 6 Step 8 client OK");
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
