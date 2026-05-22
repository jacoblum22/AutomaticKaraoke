# Phase 1 — Frontend Only (Mock Backend)

**Parent doc:** [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)  
**Prerequisite:** [PHASE_0.md](./PHASE_0.md) complete (34/34)  
**Estimated time:** 4–8 hours  
**Goal:** Real upload UX, simulated job progress, and video preview — **no** Modal ML, **no** real audio processing.

**Out of scope for Phase 1:** Demucs, Whisper, FFmpeg, R2 uploads, real `POST /start-job` to Modal, presigned uploads, auth, payments.

### Current progress

| Status | Steps |
|--------|--------|
| **Phase 1 complete** | **1–8** — ready for [Phase 2](./IMPLEMENTATION_PLAN.md#phase-2--backend-shell-only-modal-no-ml) |

**Production (mock):** https://automatic-karaoke.vercel.app — `VITE_USE_MOCK=true` on Vercel Production (`7e0518d` on `main`).

**Next after Phase 1:** [Phase 2 — Backend shell](./PHASE_2.md) (real Modal endpoints, still stub pipeline).

---

## Entry criteria

Before starting Phase 1:

- [x] [Phase 0 exit](./PHASE_0.md#exit-criteria--phase-1) satisfied (34/34)
- [x] `cd frontend && npm run build` passes on `main`
- [x] Vercel project **`automatic-karaoke`** only
- [x] `frontend/src/types/job.ts` unchanged contract

---

## Architecture (Phase 1)

```text
User selects audio file
       ↓
UploadForm (validate) → startJob(file)
       ↓
mockJobApi OR real fetch (Phase 2+)
       ↓
job_id → poll getJobStatus every 2s
       ↓
ProgressTracker (status / progress / message)
       ↓
status === "done" → VideoPlayer(video_url)
```

**Mock strategy (recommended):** In-browser mock adapter behind `client.ts`, enabled with `VITE_USE_MOCK=true`. Works on `npm run dev`, `vite preview`, and **Vercel** without a separate server.

| Approach | Local dev | Vercel preview | Phase 2 swap |
|----------|-----------|----------------|----------------|
| **In-browser mock** (`src/mocks/`) | ✓ | ✓ with env var | Set `VITE_USE_MOCK=false` |
| MSW only | ✓ | Awkward (service worker) | Extra setup |
| json-server / Modal mock | ✓ | ✗ static hosting | Not recommended |

**Do not** point `VITE_API_URL` at `localhost` on Vercel for Phase 1 mock — use `VITE_USE_MOCK=true` instead so no network call is made.

---

## Target repository tree (Phase 1 changes)

Only **`frontend/`** changes in Phase 1. No `backend/` edits.

```text
frontend/
├── .env.example                    (update) — VITE_USE_MOCK, VITE_API_URL
├── public/
│   ├── sample.mp4                  (content) — short placeholder karaoke/output clip
│   └── …
└── src/
    ├── App.tsx                     (content) — orchestrates upload → poll → player
    ├── App.css                     (content) — layout for real UI
    ├── api/
    │   └── client.ts               (content) — startJob, getJobStatus; mock switch
    ├── components/
    │   ├── UploadForm.tsx          (content)
    │   ├── ProgressTracker.tsx     (content)
    │   └── VideoPlayer.tsx         (content)
    ├── hooks/
    │   └── useJobPolling.ts        (content) — poll loop, cleanup on unmount
    ├── lib/
    │   └── validateAudio.ts        (content) — type/size checks
    ├── mocks/
    │   ├── mockJobApi.ts           (content) — in-memory jobs + stage timer
    │   └── smokeTest.ts            (content) — dev console smoke via client
    └── scripts/
        ├── smoke-mock.mjs          (content) — Step 2 gate
        └── smoke-client-run.ts     (content) — Step 3 gate (`npm run smoke:client`)
```

**Not created in Phase 1:**

| Path | Phase |
|------|-------|
| `backend/` endpoint implementations | 2 |
| MSW `src/mocks/handlers.ts` | optional; not required for exit |
| Real user upload to R2 | 2+ |

---

## API contract (same as Phase 2)

Implement against types in `frontend/src/types/job.ts`. Mock must honor this shape.

### `POST /start-job` (logical — mock implements in-process)

- **Input:** `File` (audio) — mock reads metadata only; does not upload bytes to a server in Phase 1.
- **Response:** `{ job_id: string }`

### `GET /job-status?job_id=`

- **Response:**

```typescript
{
  job_id: string;
  status: JobStatus;  // queued | separating | transcribing | aligning | rendering | done | failed
  progress?: number;  // 0–100
  message?: string;
  video_url?: string; // when done — mock returns /sample.mp4 or public URL
  error?: string;     // when failed
}
```

### Mock timing (suggested)

| Stage | Duration (mock) | `status` |
|-------|-----------------|----------|
| Start | 0s | `queued` |
| 1 | ~1.5s | `separating` |
| 2 | ~1.5s | `transcribing` |
| 3 | ~1.5s | `aligning` |
| 4 | ~1.5s | `rendering` |
| Done | — | `done` + `video_url` + `progress: 100` |

Total ~6–8s simulated pipeline — enough to test polling without boring waits.

Optional: `?fail=1` query flag in dev to test `failed` state (document in mock).

---

## File minimums

### `frontend/.env.example`

```env
# Phase 1: use in-browser mock (no network)
VITE_USE_MOCK=true

# Phase 2+: Modal base URL; ignored when VITE_USE_MOCK=true
VITE_API_URL=https://your-workspace--karaoke-api.modal.run
```

### `frontend/.env.local` (gitignored, for local dev)

```env
VITE_USE_MOCK=true
```

### `frontend/src/lib/validateAudio.ts`

- Max size: **50 MB**
- Allowed MIME types: `audio/mpeg`, `audio/wav`, `audio/x-wav`, `audio/mp4`, `audio/x-m4a`, `audio/flac`, `audio/ogg` (and/or extension fallback)
- Return `{ ok: true }` or `{ ok: false, error: string }`

### `frontend/src/mocks/mockJobApi.ts`

- In-memory `Map<job_id, JobState>`
- `createJob(file: File): Promise<StartJobResponse>` — generates UUID `job_id`, schedules stage transitions with `setTimeout`
- `getJobStatus(jobId: string): Promise<JobStatusResponse>`
- On `done`, set `video_url` to `/sample.mp4` (relative to site origin — works on Vercel)

### `frontend/src/api/client.ts`

```typescript
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

export async function startJob(file: File): Promise<StartJobResponse> {
  if (USE_MOCK) return mockCreateJob(file);
  // Phase 2: fetch(`${API_BASE}/start-job`, { method: "POST", body: ... })
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  if (USE_MOCK) return mockGetJobStatus(jobId);
  // Phase 2: fetch(`${API_BASE}/job-status?job_id=${jobId}`)
}
```

### `frontend/src/hooks/useJobPolling.ts`

- Args: `jobId: string | null`, `onUpdate`, `onTerminal` (done/failed)
- Poll every **2000 ms** while `jobId` set and status not terminal
- `useEffect` cleanup: clear interval on unmount or new job
- Stop polling on `done` | `failed`

### `frontend/src/components/UploadForm.tsx`

- Drag-and-drop zone + hidden `<input type="file" accept="audio/*">`
- Show selected **filename** and **size** (human-readable KB/MB)
- Disable submit while job running (prop from parent)
- `onSubmit(file: File)` callback after validation
- Show validation error inline

### `frontend/src/components/ProgressTracker.tsx`

- Props: `status`, `progress?`, `message?`, `error?`
- Visual: step list or progress bar for all `JobStatus` values
- Hidden or idle when no active job

### `frontend/src/components/VideoPlayer.tsx`

- Props: `src: string | null`
- `<video controls src={src} />` when `src` set
- Empty state when no video

### `frontend/public/sample.mp4`

- Short MP4 (5–15s is fine), &lt; 5 MB preferred for repo size
- Royalty-free / self-made clip only
- If you refuse to commit video: use a stable public HTTPS URL in mock `video_url` instead (document URL in `mockJobApi.ts`)

### `frontend/src/App.tsx`

- State: `selectedFile`, `jobId`, `jobStatus`, `videoUrl`, `error`
- Flow: upload → `startJob` → poll → show player on done
- Remove “Phase 0 scaffold” copy; subtitle e.g. “Phase 1 — mock pipeline”
- Reset button to start over (optional but useful)

---

## Step-by-step execution order

Complete in order. Each **Gate** must pass before the next step.

### Step 1 — Sample video + validation helper

| # | Action |
|---|--------|
| 1.1 | Add `public/sample.mp4` (or choose external URL for mock `video_url`) |
| 1.2 | Implement `src/lib/validateAudio.ts` |
| 1.3 | Quick sanity: import validator in a one-line test or `npm run build` |

**Gate:**

- [x] `sample.mp4` plays when opened directly in browser (`/sample.mp4` in dev) — ~46 KB test clip
- [x] Validator rejects non-audio; accepts `.mp3`

---

### Step 2 — Mock job API (isolated)

| # | Action |
|---|--------|
| 2.1 | Create `src/mocks/mockJobApi.ts` with stage timer |
| 2.2 | Temporarily call from `App.tsx` or `node`/`vitest` — optional |

**Gate:**

- [x] `mockCreateJob` returns `job_id`; `mockGetJobStatus` walks `queued` → … → `done` with `video_url` `/sample.mp4`
- [x] Total mock run completes in &lt;15s (~7.5s)

**First testable point:** mock API only — run `npx tsx scripts/smoke-mock.mjs` from `frontend/`, or open dev server and check console for `[Phase 1 smoke]`.

---

### Step 3 — API client + env switch

| # | Action |
|---|--------|
| 3.1 | Update `client.ts` with `startJob` / `getJobStatus` + `VITE_USE_MOCK` |
| 3.2 | Update `.env.example` and create `.env.local` with `VITE_USE_MOCK=true` |

**Gate:**

- [x] With `VITE_USE_MOCK=true`, job flow uses in-process mock (**no** `fetch` to localhost/Modal)
- [x] `npm run build` succeeds

| 3.x | Done? |
|-----|-------|
| 3.1 `client.ts` | [x] `startJob`, `getJobStatus`, `USE_MOCK` |
| 3.2 `.env.example` + `.env.local` | [x] |

**Second testable point (API layer):** `npm run smoke:client` (vite-node + `.env.local`), or restart `npm run dev` and check console `[Phase 1 smoke] client API OK` + footer **Mock mode: on**.

---

### Step 4 — `useJobPolling` hook

| # | Action |
|---|--------|
| 4.1 | Implement `hooks/useJobPolling.ts` |
| 4.2 | Wire in `App.tsx` with `console.log` or status display |

**Gate:**

- [x] Polling stops after `done` or `failed` (`App` clears `jobId` on terminal; hook effect cleans up interval)
- [x] Changing `jobId` or unmounting clears interval (cancelled flag + `clearInterval` in `useJobPolling`)

---

### Step 5 — UI components

| # | Action |
|---|--------|
| 5.1 | `UploadForm.tsx` |
| 5.2 | `ProgressTracker.tsx` |
| 5.3 | `VideoPlayer.tsx` |
| 5.4 | `App.css` — centered layout, accessible labels |

**Gate:**

- [x] Invalid file shows error without starting job (`validateAudio` in `UploadForm`)
- [x] Valid file shows name + size
- [x] Progress shows each pipeline stage during mock run (`ProgressTracker` + mock stages)

**Third testable point:** full flow in `npm run dev` without Vercel (upload → mock progress → `/sample.mp4` plays).

---

### Step 6 — App integration

| # | Action |
|---|--------|
| 6.1 | `App.tsx` wires upload → startJob → poll → VideoPlayer |
| 6.2 | Handle `failed` with error message |
| 6.3 | Optional: “Process another song” reset |

**Gate:**

- [x] End-to-end happy path works locally (`npm run dev`)
- [x] `npm run lint` passes
- [x] `npm run build` passes

---

### Step 7 — Vercel preview with mock

| # | Action |
|---|--------|
| 7.1 | Vercel → **automatic-karaoke** → Settings → Environment Variables |
| 7.2 | Add `VITE_USE_MOCK` = `true` for **Production** (and **Preview** if you use PR previews) |
| 7.3 | Keep or remove `VITE_API_URL` on Vercel — ignored when mock is true; can leave placeholder |
| 7.4 | Push to `main`; wait for deploy |
| 7.5 | Test full upload flow on https://automatic-karaoke.vercel.app |

**Gate:**

- [x] Production deploy shows Phase 1 UI (not “Phase 0 scaffold”)
- [x] Mock job completes; sample video plays on production URL
- [x] `VITE_USE_MOCK=true` on Vercel Production; no fetch to API when mock is on

**Do not** deploy a second Vercel project from `npx vercel --yes` in `frontend/` — use GitHub-linked **`automatic-karaoke`** only ([Phase 0 lesson](./PHASE_0.md#lessons-learned-phase-0-retrospective)).

---

### Step 8 — Docs + README

| # | Action |
|---|--------|
| 8.1 | Update root `README.md` — current phase Phase 1 complete, how to run mock flow |
| 8.2 | Check off [completion checklist](#phase-1-completion-checklist) below |
| 8.3 | Commit + push to `main` |

**Gate:**

- [x] GitHub `main` has Phase 1 code (`7e0518d`); Vercel production deploy succeeded

---

## Phase 1 completion checklist

**All required boxes checked** ✓ — safe to start [Phase 2](./IMPLEMENTATION_PLAN.md#phase-2--backend-shell-only-modal-no-ml).

### Mock + API layer

- [x] `src/mocks/mockJobApi.ts` implements full status progression
- [x] `src/api/client.ts` exports `startJob` and `getJobStatus` with mock switch
- [x] `VITE_USE_MOCK=true` documented in `.env.example` + `.env.local`
- [x] No network calls during mock flow (`npm run smoke:client`)

### UI components

- [x] `UploadForm` — drag/drop, picker, filename, size, validation errors
- [x] `ProgressTracker` — all statuses including `aligning`
- [x] `VideoPlayer` — plays `sample.mp4` (or configured URL) on `done`
- [x] `App.tsx` orchestrates full flow; Phase 0 placeholder copy removed

### Hooks / lib

- [x] `useJobPolling` — 2s interval, stops on `done`/`failed`, cleanup on unmount
- [x] `validateAudio` — 50 MB + audio types

### Assets

- [x] `public/sample.mp4` exists (or external `video_url` documented)

### Verification

- [x] Invalid upload shows error (UI + `smoke:mock` validates `validateAudio`)
- [x] `npm run build` passes
- [x] `npm run lint` passes
- [x] Local `npm run dev` — full happy path
- [x] https://automatic-karaoke.vercel.app — full happy path with `VITE_USE_MOCK=true`

### Explicitly NOT done (confirm)

- [x] No real upload to backend / R2
- [x] No Modal `web_endpoint` calls
- [x] No changes to `backend/` pipeline logic
- [x] No Demucs / Whisper / FFmpeg

---

## Exit criteria → Phase 2

Phase 1 is **complete** ✓ (May 2026):

1. [x] [Completion checklist](#phase-1-completion-checklist) — all required items checked.
2. [x] Upload on **local** and **Vercel** → mock progress → sample video — no GPU work.
3. [x] `client.ts` has real `fetch` paths behind `!isMockMode()` (`start-job`, `job-status`) matching `job.ts` types.
4. [x] `.env.example` documents Phase 2: `VITE_USE_MOCK=false` + `VITE_API_URL` (Modal base URL).

**Next:** [Phase 2 — Backend shell](./IMPLEMENTATION_PLAN.md#phase-2--backend-shell-only-modal-no-ml) — Modal `start-job` / `job-status`, stub orchestrator, CORS for `automatic-karaoke.vercel.app`.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Video 404 on Vercel | Ensure `sample.mp4` is under `frontend/public/` and path is `/sample.mp4` |
| Polling never stops | Check terminal status handling; ensure `done`/`failed` clear interval |
| Fetch to localhost on Vercel | Set `VITE_USE_MOCK=true`; rebuild deploy |
| `VITE_*` not updating locally | Restart `npm run dev` after `.env.local` change |
| Upload accepts huge files | Enforce `validateAudio` before `startJob` |
| React strict mode double timers | Guard mock so duplicate `createJob` doesn’t orphan intervals, or use refs in hook |

---

## Optional enhancements (not required for exit)

- MSW for dev-only network interception (parity testing before Phase 2)
- “Simulate failure” dev button calling mock with forced `failed`
- Basic responsive CSS / dark mode
- `vite preview` documented as local production-like test before push

---

*Phase 1 runbook v1.3 — **complete** (Steps 1–8). Next: [Phase 2](./IMPLEMENTATION_PLAN.md#phase-2--backend-shell-only-modal-no-ml).*
