/**
 * Measure how long start-job blocks for different payload sizes.
 * Run: npm run measure:start-job  (uses .env.modal or .env.local)
 */
import { API_BASE, isMockMode, startJob } from "../src/api/client";

const SIZES = [
  { label: "100 B", bytes: 100 },
  { label: "100 KB", bytes: 100 * 1024 },
  { label: "1 MB", bytes: 1024 * 1024 },
  { label: "5 MB", bytes: 5 * 1024 * 1024 },
];

console.log("API_BASE:", API_BASE);
console.log("mock mode:", isMockMode());
console.log("");

for (const { label, bytes } of SIZES) {
  const file = new File([new Uint8Array(bytes)], "timing.mp3", {
    type: "audio/mpeg",
  });
  const t0 = performance.now();
  try {
    const { job_id } = await startJob(file);
    const ms = performance.now() - t0;
    console.log(`${label.padEnd(8)} → ${ms.toFixed(0)} ms  job_id=${job_id.slice(0, 8)}…`);
  } catch (err) {
    console.log(`${label.padEnd(8)} → ERROR`, err);
  }
}

console.log("\nNote: Modal mode includes upload time + cold start until HTTP response.");
