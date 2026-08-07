# Project Retrospective — HeaviAI Procurement CoPilot

**Built:** April 2026  
**Stack:** FastAPI + React + Supabase + Claude + Cohere → Railway

---

## What We Built

A greenfield full-stack AI application for fleet operators to procure commercial truck parts. The operator enters a VIN and a natural language description of what they need. The system decodes the VIN, parses intent, runs a hybrid retrieval pipeline (pgvector semantic search + SQLite BM25 full-text search merged with Reciprocal Rank Fusion), reranks with Cohere, and assesses per-part fitment against the specific vehicle using Claude. Results stream to the UI in real time via SSE. Orders are persisted in Supabase.

---

## Build Phases

### Phase 1 — Architecture & Planning
Defined the full system architecture before writing a single line of code. Produced `build-plan.md` with a complete file tree, schema definitions, pipeline flow, and batched implementation order. Documented every major technical decision in `design-decisions.md` before committing to it.

**Time investment:** High upfront, paid off — almost no architectural backtracking during implementation.

### Phase 2 — Backend (Batches 1–7)
Built in parallel batches: schemas → DB clients → pipeline modules → API routes → ingestion. The pipeline (intent → embed → retrieve → rerank → fitment → stream) was implemented as stateless async functions with clean interfaces between each step.

### Phase 3 — Frontend (Batches 8–10)
React SPA with two-screen flow: landing form → results page via React Router state. SSE streaming with per-card fade-in animations as parts arrive. Client-side filters applied to the already-streamed results array.

### Phase 4 — UI Redesign
Rethemed to black/orange industrial design, enlarged components for tablet/gloved use, renamed to "HeaviAI Procurement CoPilot", split into landing + results screens, added price and year range filters.

### Phase 5 — Bug Fixes & Testing
Systematic edge case testing uncovered real bugs. Fixed and documented each in `debug-decisions.md`. Ran a pre-deployment test suite before touching Railway.

### Phase 6 — Deployment
Deployed two Railway services from a monorepo. Required several iterations to get right. Both services are now live with GitHub-connected auto-deploys on push to `main`.

### Phase 7 — Documentation
`code-explainability.md` (54 entries, every source file), `design-decisions.md`, `debug-decisions.md`, `deployment-steps.md`, `manual-test-cases.md`, updated `README.md`.

---

## What Went Well

### Hybrid retrieval pipeline
Combining pgvector ANN and SQLite BM25 with RRF worked well in practice. Neither retriever alone would catch all relevant parts — semantic search handles synonyms and descriptions, BM25 catches exact part numbers. Running them concurrently with `asyncio.gather` kept latency low.

### SSE streaming UX
Streaming results one card at a time rather than waiting for all 10 to be scored felt fast and responsive. The skeleton loader → animated card fade-in sequence gave the UI a live, working feel even on slower queries.

### Upfront architecture document
Writing `build-plan.md` before any code meant implementation was mostly mechanical — each file had a clear spec. No "what should this do?" moments mid-build. The batched parallel implementation order meant no waiting.

### Pre-deployment testing
Running the 8-item test suite before touching Railway caught the Supabase module path issue and confirmed SSE headers, CORS, FTS cold-start rebuild, and urgency routing all worked. Saved at least one failed deployment cycle.

### Documentation discipline
Maintaining `debug-decisions.md` with root cause + fix for every bug created a searchable record of why things are the way they are. `code-explainability.md` with a consistent format per file makes onboarding straightforward.

### Dark industrial UI
The black/orange theme with oversized tap targets came together cleanly. The two-screen flow (landing → results) gave each screen a single clear job.

---

## What Could Have Gone Better

### Real credentials in `.env.example`
The `.env.example` file was committed with live API keys. This is a serious security issue — those credentials were briefly public on GitHub. Keys should have been rotated immediately (Supabase service key, Anthropic key, Cohere key, Browserbase key). `.env.example` should always contain placeholder strings only.

**Lesson:** Never put real values in any file that isn't in `.gitignore`. Treat `.env.example` as a public document.

### Railway deployment took multiple iterations
Four separate deployment errors before both services were stable:
1. Invalid `[[services]]` blocks in `railway.toml` (not a real Railway construct)
2. Backend hardcoded to port `8000` instead of `$PORT`
3. Frontend nginx hardcoded to port `80` instead of `$PORT`
4. `VITE_API_BASE_URL` set to `localhost:8000` — set after the build ran, requiring a full redeploy

All four were avoidable with prior knowledge of Railway's config format and build-time vs runtime variable distinction.

**Lesson:** Read the target platform's config-as-code docs before writing deployment config. For Railway specifically: only `[build]` and `[deploy]` are valid top-level sections; `$PORT` is always dynamic; `VITE_*` vars are build-time only.

### `railway up` uploads repo root, not current directory
Running `railway up` from `backend/` still uploaded the entire git repo root, triggering Railpack auto-detection on the root which has no recognizable app. This forced switching to GitHub-connected deploys with Root Directory set per service in the dashboard.

**Lesson:** For Railway monorepo deployments, skip `railway up` entirely. Connect GitHub from the start and set Root Directory per service in the dashboard.

### Missing component entries in `code-explainability.md`
Five components (`SearchBar`, `PartCard`, `PartDetail`, `OrderConfirm`, `OrderHistory`) were referenced throughout the document but never had their own entries. Caught and fixed in a final audit pass.

**Lesson:** Add code-explainability entries at the time of writing each file, not in a batch at the end. Easier to write while the code is fresh.

### VIN validation bug shipped undetected
The submit button accepted any 17-character string as valid (enabled after 17 chars regardless of VIN lookup result), and an invalid VIN showed a tick mark with no text. Both were found during manual testing rather than being caught upfront.

**Lesson:** Write the disabled condition for form submit buttons to explicitly cover every invalid state, and test the error path for every async call (null return, partial data) before shipping.

### `SearchPage.tsx` carried too much state initially
The original single-page design had all search + results + modal state in one component. The two-screen refactor (landing → results page) was the right call but required a full rewrite of the page layer. The architecture decision to split was correct; making it earlier would have saved a rewrite.

**Lesson:** For flows with distinct "before search" and "after search" states, design as separate screens from the start.

---

## By the Numbers

| Metric | Count |
|--------|-------|
| Source files written | ~55 |
| Lines of code (approx) | ~5,500 |
| Bugs found and fixed | 20 (documented in debug-decisions.md) |
| Pre-deployment tests run | 8 |
| Railway deployment iterations | 4 |
| Documentation files | 8 |
| Test cases (manual-test-cases.md) | 25 |
| Parts in catalog | 170 |
| VINs seeded | 26 |

---

## If Starting Again

1. Read Railway docs before writing any deployment config
2. Never put real credentials anywhere near a tracked file — not even temporarily
3. Add `code-explainability.md` entries file by file as you write, not in a batch
4. Design the two-screen flow from the start rather than refactoring from a single page
5. Test the VIN error path (null return + empty fields) during initial SearchBar development
6. Use GitHub-connected Railway deploys from day one — skip `railway up` for monorepos
