# Parts Procurement CoPilot — Agent-Assisted Development Session

This document covers how a Claude coding agent (via Claude Code's `/plan` workflow — plan first, approve, then execute) was used to build a full-stack AI parts procurement system across two feature phases. The throughline: the human owns every architectural decision and root-cause hypothesis; the agent owns parallel code execution and cross-file consistency. Plan before touching code, parallelise everything that can be parallelised, keep fixes minimal, document every failure. 25 errors logged, all resolved.

---

## 1. The System

**v1.0:** Hybrid AI search pipeline — VIN decode, intent parsing, BM25 + pgvector retrieval, rerank, fitment scoring, SSE streaming. Parts catalog ingestion and orders page.

**v2.0:** Vendor outreach agent — vendor selection, AI-generated outreach email, simulated vendor responses, response parsing, follow-up generation, composite scoring, live job board.

Across both phases: FastAPI backend, React frontend, Supabase, offline ingestion pipeline, two Railway services.

---

## 2. Division of Responsibility

**Human:**
- Defined requirements, architecture, and system boundaries
- Broke the problem into ordered batches with checkpoint criteria
- Ran all checkpoints, diagnosed failures, forced pivots when behavior diverged from spec
- Made all design tradeoffs

**Agent:**
- Translated batch specs into code, writing independent files in parallel within each batch
- Given a hypothesis from the human, confirmed the root cause in code and wrote the minimal fix
- Maintained cross-file consistency (schema field names, import paths, state access patterns)

---

## 3. How the Human Broke Down the Problem

### Plan before code

Every feature started with `/plan`. The agent drafted an implementation plan; the human reviewed and approved before any code was written. For v2.0 this produced 11 explicit batches with dependency ordering and checkpoint criteria defined upfront — design decisions resolved in the plan (e.g. asyncio coroutine vs `BackgroundTasks` for the worker) cost one review cycle rather than a post-implementation refactor.

### Checkpoints

| Checkpoint | Criterion |
|---|---|
| CP-1 | SQL schema applied to Supabase |
| CP-2 | `uvicorn` boots, Supabase client connects |
| CP-3 | Ingestion runs, parts visible in DB |
| CP-4 | `/search` SSE returns results |
| CP-5 | Eval runner passes 5/5 golden queries |
| CP-6 | v2.0 final: full vendor outreach state machine end-to-end |

The agent did not move to the next batch until the human confirmed the checkpoint passed.

### Batch parallelism

Independent files were written in a single agent turn. v2.0 Batch 5 (five AI agent modules) and Batch 10 (four frontend components) were each a single message with parallel writes — one turn for five files instead of five.

---

## 4. v1.0 Build

### Human-specified architecture

- **Scraping via Browserbase + Playwright**: finditparts.com requires a real browser (JS rendering, anti-bot). Browserbase provides a managed remote Chromium session with residential proxy rotation. Playwright connects via CDP — scraper logic stays separate from browser infra
- **Hybrid retrieval**: SQLite FTS5 (BM25) + Supabase pgvector merged via RRF — BM25 for keyword precision, pgvector for semantic queries, RRF normalises both ranked lists without score calibration
- **No task queue**: In-process async + SSE streaming — eliminates Redis + Celery for the scale of this tool
- **Single Supabase instance**: PostgreSQL + pgvector + JSONB — free tier, covers all data needs
- **Urgency → model swap**: Urgent uses Haiku (lower latency), standard uses Sonnet — same pipeline, model injected as parameter
- **Client-side filters**: Results filtered in browser against the streamed array, no re-query on filter change
- **Orders as intent records**: No payment, no external integration

### Agent execution

- `requestSubmit()` and `.product_results_grid.loaded` scoping — identified by the human from site inspection, implemented by the agent
- `asyncio.gather` for parallel BM25 + pgvector retrieval — plan specified parallel retrieval, agent chose `gather` as the mechanism
- `check_same_thread=False` for SQLite — agent identified the threading constraint (connection on main thread, queries from `run_in_executor`)

---

## 5. v1.0 Pivots (1–2)

### Pivot 1 — Scraper returning 0 parts
Human ran `loader.py`, got 0 parts. Human identified from site inspection: the search form uses Hotwire Turbo Frame navigation, requiring JS form submission (`requestSubmit()`) rather than a `.click()` on the button; the page renders a skeleton `.product_results_grid.loading` alongside the real `.product_results_grid.loaded` simultaneously, requiring selectors scoped to `.loaded`. Agent rewrote `scraper.py` with both corrections. A second run surfaced the Klaviyo popup — human identified it as the cause of intermittent pointer blocking on other interactions; agent added `_dismiss_popup` to clear it. `requestSubmit()` handles the form submit and is immune to pointer blocking regardless; `_dismiss_popup` prevents the modal from interfering with any subsequent page interactions.

### Pivot 2 — Clarify banner had no input
Human tested the clarify flow: triggering a clarify question showed only a back button that navigated away. Human specified: inline input that re-searches with the amended query without leaving the page. Agent added `clarifyAnswer` state, replaced the nav button with a form, wired `handleClarifySubmit` to re-call `streamSearch` with `"${original} — ${answer}"`.

---

## 6. v2.0 Build

### Human-specified state machine

```
created
  └─ [user] → outreach_sent
       └─ [worker: simulate + parse]
            ├─ missing fields → follow_up_required
            │      └─ [user] → follow_up_sent → [worker] → parsed
            └─ all fields → parsed
                 └─ [user: Confirm] → confirmed    ← human gate
                        └─ [worker: score] → ranked
                               ├─ [user: Accept] → accepted
                               └─ [user: Reject] → rejected
```

Two human gates: confirm before ranking, accept/reject after. Agent implemented as `POST /jobs/{id}/confirm` with status guard + sticky-footer button.

### Batch structure

```
1  → DB migration
2  → Pydantic schemas
3  → DB query functions
4  → vendor_seeder.py           ─── parallel
5  → 5 AI agent modules         ─── parallel
6  → Worker loop
7  → vendors.py, procurement.py ─── parallel
8  → main.py (router + worker start)
9  → Frontend types + API clients ── parallel
10 → 4 frontend components      ─── parallel
11 → Page integration
```

---

## 7. v2.0 Pivots (3–8)

### Pivot 3 — Invalid VIN accepted
Human entered "AUMMMSO0" (8 chars, contains 'O'). System returned an empty VINSpec instead of rejecting. Human specified: validate 17-char length, exclude I/O/Q per VIN standard, reject before NHTSA call, treat no make/model in NHTSA response as invalid. Agent added `_VIN_RE = re.compile(r'^[A-HJ-NPR-Z0-9]{17}$', re.IGNORECASE)` as early guard in `decoder.py` plus null-check on NHTSA response.

### Pivot 4 — Worker auto-confirming without human review
Human observed jobs going directly from `parsed` to `ranked`. Original plan had the worker setting `status="confirmed"` when all fields parsed. Human specified: worker stops at `parsed`, `confirmed` requires user action. Agent changed `new_status = "confirmed"` → `"parsed"` in `_run_simulation`, added the `/confirm` endpoint and confirm button.

### Pivot 5 — Delivery score always 0% for 20-day vendors
Human noticed the delivery bar showing 0% for certain vendors. Human pointed to the ranker — agent found `_DELIVERY_CEILING_HOURS = 480` (20 days). The ceiling was set at the upper bound of realistic vendor lead times rather than beyond it, so vendors at that bound scored exactly 0. Human raised the ceiling to 720h (30 days) to represent the outer edge of acceptable delivery — any vendor genuinely at 30 days is already outside range for the use case, and 20-day vendors now score 33%. Agent updated the constant and the formula in `VendorOutreachPanel.tsx`.

### Pivot 6 — Jobs stalling at `confirmed`
Human observed jobs stuck with no transition to `ranked`. Human suggested `_rank_job` may be silently returning — agent confirmed: the function bailed early when `delivery_hours is None`, and `delivery_hours` had two paths to get there: the vendor_part seeded integer was absent on a fetch miss, and the LLM-parsed delivery text was stored as a string but never converted to an integer. Either failure left the ranking function with nothing to work with. Agent removed the bail-out, added `delivery_text_to_hours()` regex parser, and wired a three-level fallback: seeded int → text parse → ceiling default.

### Pivot 7 — Confirm button not visible at `parsed`
Human opened a `parsed` job, saw no way to advance. The button was buried in the scrollable body below vendor info, outreach email, vendor response, and parsed fields. Human specified: sticky footer matching the `ranked` accept/reject pattern. Agent removed the button from the body, added sticky footer conditional on `parsed` or `ranked` status.

### Pivot 8 — Response rate bar missing from ranking score
Human saw only price and delivery bars — no response rate. Human suspected missing vendor data in the response. Agent confirmed three compounding issues: action endpoints returned raw `update_procurement_job` results (no vendor join → `vendor = None`); `handleJobUpdate` fully replaced the selected job (losing vendor from initial fetch); `{job.vendor && <ScoreBar/>}` silently disappeared. Fix: `_fetch_job()` re-fetches with `vendor:vendors(*)` join after every action; `handleJobUpdate` uses spread-merge `{ ...prev, ...updated }`.

---

## 8. Debug Pattern

```
Human runs checkpoint
  → observes wrong behavior, suggests likely cause

Agent reads those files
  → confirms or refines hypothesis, states root cause in one sentence

Agent writes minimal fix — no adjacent cleanup, no speculative guards

Human re-runs checkpoint

Agent documents in debug-decisions.md: root cause, fix, prevention rule
```

Documenting root causes built a pattern library across 25 errors. The PostgREST "filter values are data, not SQL" category appeared in v1.0 (Supabase URL handling) and again in v2.0 (`fetch_pending_simulations` using the string `"now()"`); the second fix was immediate from the prior entry.

| Category | Count |
|---|---|
| Human spec change | 4 |
| Scraper / DOM | 3 |
| Pydantic / settings | 3 |
| PostgREST / Supabase | 3 |
| Railway / deployment | 3 |
| Frontend state | 3 |
| Async / threading | 2 |
| Ranking / scoring | 2 |
| LLM output | 2 |

---

## 9. Architecture

```
Browser
  ├── GET /vin/{vin}                  VIN decode
  ├── POST /search                    SSE: 7-step AI pipeline
  ├── GET /vendors/part/{part_id}     Vendor list
  ├── POST /procurement/jobs          Create job + outreach email
  └── POST /procurement/jobs/{id}/*   State transitions
         │
    FastAPI + asyncio (Railway)
         │                  │
    ┌────┴──────────────┐   │   External APIs
    │  Search (SSE):    │   ├── Claude Sonnet   intent, fitment
    │  VIN → intent     │   ├── Claude Haiku    vendor email agents
    │  → embed → ret.   │   ├── Cohere          embeddings, rerank
    │  → rerank → fit.  │   └── NHTSA VPIC      VIN decode (cached)
    │  → stream         │
    │                   │
    │  Vendor worker    │
    │  (30s poll):      │
    │  sim → parse      │
    │  → followup       │
    │  → rank           │
    └────┬──────────────┘
         │
    ┌────┴─────────────────┐    ┌──────────────────┐
    │  Supabase            │    │  SQLite FTS5      │
    │  parts, orders       │    │  BM25, in-        │
    │  vin_cache, vendors  │    │  container        │
    │  vendor_parts        │    └──────────────────┘
    │  procurement_jobs ───┼── Realtime ──→ Browser
    │  procurement_events  │
    └──────────────────────┘
```

| Transition | Actor |
|---|---|
| `created → outreach_sent` | User |
| `outreach_sent → parsed / follow_up_required` | Worker |
| `follow_up_required → follow_up_sent` | User |
| `follow_up_sent → parsed` | Worker |
| `parsed → confirmed` | **User** (human gate) |
| `confirmed → ranked` | Worker |
| `ranked → accepted / rejected` | **User** (human gate) |
