/**
 * Step 3 gate — runs under vite-node with .env.local loaded.
 */
import { validateAudio } from "../src/lib/validateAudio";
import { getJobStatus, isMockMode, startJob } from "../src/api/client";

const good = new File([new Uint8Array(100)], "a.mp3", { type: "audio/mpeg" });
if (!validateAudio(good).ok) {
  console.error("validateAudio FAIL");
  process.exit(1);
}

if (!isMockMode()) {
  console.error("VITE_USE_MOCK must be true (check .env.local)");
  process.exit(1);
}

const { job_id } = await startJob(good);
let last = "";
for (let i = 0; i < 30; i++) {
  const s = await getJobStatus(job_id);
  if (s.status !== last) {
    console.log(s.status, s.progress, s.video_url ?? "");
    last = s.status;
  }
  if (s.status === "done" && s.video_url === "/sample.mp4") {
    console.log("client API OK (mock, no fetch)");
    process.exit(0);
  }
  if (s.status === "failed") {
    console.error("client API FAIL", s);
    process.exit(1);
  }
  await new Promise((r) => setTimeout(r, 400));
}
process.exit(1);
