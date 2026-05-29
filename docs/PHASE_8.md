# Phase 8 — Frontend polish & UX

**Parent doc:** [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)  
**Prerequisite:** [PHASE_7.md](./PHASE_7.md) exit (production pipeline live on Vercel + Modal)  
**Estimated time:** 8–16 hours (incremental; shippable after each step)  
**Goal:** Make https://automatic-karaoke.vercel.app feel like a **real product** — clearer hierarchy, better upload/progress/video states, responsive layout — **without** changing the async API or pipeline.

**Out of scope for Phase 8:** Lyric editor, auth/payments, new backend routes, reference-lyrics API (see v2 backlog in IMPLEMENTATION_PLAN).

### Current progress

| Status | Steps |
|--------|--------|
| **Done** | **1** — design tokens + layout shell (Tailwind v4, `smoke_phase8_step1.py`) |
| **Done** | **2** — shadcn/ui (`Button`, `Card`, `Progress`, `Alert`, `Badge`; `smoke_phase8_step2.py`) |
| **Done** | **3** — upload + primary CTA polish (`smoke_phase8_step3.py`) |
| **Done** | **4** — progress + error states (`smoke_phase8_step4.py`) |
| **Done** | **5** — video result + empty states (`smoke_phase8_step5.py`) |
| **Done** | **6** — hide dev footer; optional metadata fields (`smoke_phase8_step6.py`) |
| **Done** | **7** — docs + sign-off (`smoke_phase8_step7.py`) |

**Shipped UI:** Tailwind v4 + shadcn/ui, hero + card layout, upload dropzone, pipeline stepper, video card, dev-only Debug footer.

---

## Entry criteria

- [ ] [Phase 7 exit](./PHASE_7.md#exit-criteria--v2--maintenance) satisfied
- [ ] `scripts/smoke_phase7_step8.py --verify-only` passes
- [ ] E2E upload → MP4 still works on production before starting

**Critical rules (unchanged):**

- Do **not** break `VITE_USE_MOCK`, presigned upload, or `X-API-Key` client headers
- Keep bundle size reasonable (avoid heavy animation libraries unless justified)
- Prefer **accessible** components (focus rings, contrast, `prefers-reduced-motion`)

---

## Design direction (suggested)

| Area | Today | Phase 8 target |
|------|--------|----------------|
| Typography | System sans | Distinct display + body pair (e.g. `Instrument Sans` + `DM Sans`, or one variable font) |
| Layout | Single narrow column | Hero + card-based main panel; comfortable max-width; mobile padding |
| Upload | Dashed box + text | Icon, hover/drag-active states, file chip with clear/remove |
| Primary button | Flat purple block | Clear disabled/loading; spinner + label change |
| Progress | Text list + thin bar | Stepper with active/completed/dim; optional ETA copy from `message` |
| Footer | Mock/API/key debug | **Production:** minimal “Powered by Modal” or hidden; **dev:** keep debug in `import.meta.env.DEV` only |
| Video | Placeholder box | Framed player, download link, “Make another” reset |

**Optional brand:** subtle gradient mesh or noise background — avoid clutter; karaoke video should stay the hero after processing.

---

## Architecture (Phase 8 additions)

No backend changes. Frontend-only:

```text
frontend/
├── src/
│   ├── components/ui/          # shadcn primitives (Button, Card, Progress, …)
│   ├── components/             # UploadForm, ProgressTracker, VideoPlayer (restyled)
│   ├── lib/utils.ts            # cn() helper if using shadcn
│   └── index.css               # Tailwind @theme tokens (if Tailwind added)
```

**Recommended stack:** [Tailwind CSS v4](https://tailwindcss.com/) + [shadcn/ui](https://ui.shadcn.com/) (copy-paste components into `src/components/ui/` — no runtime UI package lock-in). Fits Vite + React; no Next.js required.

**Alternatives:** Radix primitives only, Mantine, or stay CSS-modules — shadcn is the default recommendation for speed + quality.

---

## Steps

### Step 1 — Tokens + layout shell

| # | Action |
|---|--------|
| 1.1 | Add Tailwind (or extend CSS variables in `index.css`) for color, radius, spacing |
| 1.2 | Refactor `App.tsx` into header / main / footer regions |
| 1.3 | Responsive breakpoints; test 375px and 1280px |

**Gate:**

- [x] `npm run build` passes
- [x] `scripts/smoke_phase8_step1.py` passes
- [ ] Layout checked at 375px and 1280px (manual)

```powershell
cd frontend
npm run dev
# other terminal:
..\.venv\Scripts\python.exe scripts\smoke_phase8_step1.py
```

---

### Step 2 — Component library bootstrap

| # | Action |
|---|--------|
| 2.1 | `npx shadcn@latest init` in `frontend/` (Vite path) |
| 2.2 | Add `Button`, `Card`, `Progress`, `Alert`, `Badge` |
| 2.3 | Replace ad-hoc classes in one component as proof |

**Gate:**

- [x] `components.json` + `src/components/ui/{button,card,progress,alert,badge}.tsx`
- [x] `App.tsx` uses `Card`; `UploadForm` uses `Button` + `Badge` + `Alert`
- [x] `scripts/smoke_phase8_step2.py` passes

```powershell
..\.venv\Scripts\python.exe scripts\smoke_phase8_step2.py
```

---

### Step 3 — Upload zone + CTA

| # | Action |
|---|--------|
| 3.1 | Drag-over highlight, keyboard accessible file input |
| 3.2 | Selected file row: name, size, remove |
| 3.3 | Primary CTA: idle / uploading / processing states |

**Gate:**

- [x] Tailwind dropzone + file chip with remove; `Progress` during draft upload; CTA spinner
- [x] `@/*` paths in `tsconfig.app.json` without deprecated `baseUrl` / `ignoreDeprecations`
- [x] `scripts/smoke_phase8_step3.py` passes
- [ ] File select → finalize still works against Modal (manual or `smoke:modal`)

```powershell
..\.venv\Scripts\python.exe scripts\smoke_phase8_step3.py
```

---

### Step 4 — Progress tracker

| # | Action |
|---|--------|
| 4.1 | Map `JobStatus` to stepper (queued → separating → … → done) |
| 4.2 | Progress bar from `progress` field; show `message` |
| 4.3 | Failed state: `Alert` with `error` + retry hint |

**Gate:**

- [x] shadcn `Progress` + stepper icons; failed `Alert` with retry copy
- [x] Hero/footer use `text-muted-foreground` (not `text-muted` background token)
- [x] `scripts/smoke_phase8_step4.py` passes
- [ ] Mock mode shows all states; production job shows live updates (manual)

```powershell
..\.venv\Scripts\python.exe scripts\smoke_phase8_step4.py
```

---

### Step 5 — Video result + empty states

| # | Action |
|---|--------|
| 5.1 | Card wrapper for `<video>`; native controls |
| 5.2 | Download / open in new tab |
| 5.3 | Empty state illustration or icon before first upload |

**Gate:**

- [x] `VideoPlayer` card + empty icon; spinner empty state while processing
- [x] Download MP4 + Open in new tab links when `video_url` is set
- [x] `scripts/smoke_phase8_step5.py` passes
- [ ] Completed production run plays inline (manual)

```powershell
..\.venv\Scripts\python.exe scripts\smoke_phase8_step5.py
```

---

### Step 6 — Dev footer + optional metadata (prep for lyrics v2)

| # | Action |
|---|--------|
| 6.1 | Move Mock/API/key footer behind `import.meta.env.DEV` or collapsible “Debug” |
| 6.2 | Optional **Song title** / **Artist** inputs (UI only; wire in lyrics phase later) |
| 6.3 | Config warning banner styled with `Alert` |

**Gate:**

- [x] Collapsible **Debug** footer in dev; production shows short Modal/Vercel line only
- [x] Optional song title / artist fields (UI only, not sent to API)
- [x] Config warning uses `AlertTitle` + `AlertDescription`
- [x] `scripts/smoke_phase8_step6.py` passes

```powershell
..\.venv\Scripts\python.exe scripts\smoke_phase8_step6.py
```

---

### Step 7 — Docs + sign-off

| # | Action |
|---|--------|
| 7.1 | Update `README.md` screenshot or one-line UX note |
| 7.2 | `scripts/smoke_phase7_step8.py --verify-only` (API wiring unchanged) |
| 7.3 | Lighthouse accessibility spot-check (contrast, buttons) |

**Gate:**

- [x] `README.md` + `IMPLEMENTATION_PLAN.md` reference Phase 8
- [x] `scripts/smoke_phase8_step7.py` runs steps 1–6 + `smoke_phase7_step8.py --verify-only`
- [x] `prefers-reduced-motion` + focus rings in theme (Lighthouse optional, manual)
- [ ] Vercel preview approved after `git push` (manual)

```powershell
..\.venv\Scripts\python.exe scripts\smoke_phase8_step7.py
```

---

## Phase 8 completion checklist

### Visual & UX

- [x] Cohesive color + typography tokens
- [x] Upload drag/drop feels responsive (hover, active, error)
- [x] Progress stepper readable on mobile
- [x] Video result is clearly the success state
- [x] Dev/debug info not prominent on production

### Regression

- [x] `npm run build` clean (via `smoke_phase8_step7.py`)
- [x] `smoke_phase7_step8.py --verify-only` passes (in step 7 smoke)
- [ ] Manual E2E: upload → done → MP4 plays

### Explicitly optional

- [ ] Dark/light theme toggle
- [ ] Custom logo / favicon
- [ ] Title + artist fields submitted to backend

---

## Exit criteria

Phase 8 is **complete** when the checklist above is satisfied and the live site no longer reads as an internal tool (debug footer hidden, polished upload → progress → video flow).

**Sign-off command:** `..\.venv\Scripts\python.exe scripts\smoke_phase8_step7.py`

**After Phase 8:** pursue **feature v2** (reference lyrics API, alignment path) or marketing (landing copy, OG image) — not more pipeline work.

---

## Tooling notes (Cursor / MCP)

| Tool | Helps with UI? |
|------|----------------|
| **shadcn/ui + Tailwind** (npm) | **Yes** — primary source of components |
| **Cursor Canvas** | Layout explorations, side-by-side mockups |
| **Figma MCP** (if enabled in Cursor) | Import design tokens / inspect frames — optional |
| **Vercel MCP** | Deploy previews, env vars — not UI kits |
| **GitKraken MCP** | Git only |

There is **no** dedicated “UI components MCP” in this repo today; components come from **shadcn**, **Radix**, or hand-built CSS.

---

*Phase 8 runbook v1.0 — frontend polish after production hardening.*
