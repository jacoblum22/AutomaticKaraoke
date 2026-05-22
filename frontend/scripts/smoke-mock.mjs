/**
 * Node smoke test for mockJobApi (Step 2 gate).
 * Run: node scripts/smoke-mock.mjs
 * Requires Node 18+ (global File).
 */
import { validateAudio } from "../src/lib/validateAudio.ts";
import { mockCreateJob, mockGetJobStatus } from "../src/mocks/mockJobApi.ts";

const bad = validateAudio(new File([new Uint8Array(1)], "x.txt", { type: "text/plain" }));
const good = validateAudio(new File([new Uint8Array(100)], "a.mp3", { type: "audio/mpeg" }));

if (!bad.ok && good.ok) {
  console.log("validateAudio OK");
} else {
  console.error("validateAudio FAIL", { bad, good });
  process.exit(1);
}

const { job_id } = await mockCreateJob(
  new File([new Uint8Array(100)], "a.mp3", { type: "audio/mpeg" })
);
console.log("job_id:", job_id);

let last = "";
for (let i = 0; i < 30; i++) {
  const s = await mockGetJobStatus(job_id);
  if (s.status !== last) {
    console.log(s.status, s.progress, s.video_url ?? "");
    last = s.status;
  }
  if (s.status === "done" || s.status === "failed") {
    if (s.status === "done" && s.video_url === "/sample.mp4") {
      console.log("mockJobApi OK");
      process.exit(0);
    }
    console.error("mockJobApi FAIL", s);
    process.exit(1);
  }
  await new Promise((r) => setTimeout(r, 400));
}

console.error("timeout");
process.exit(1);
