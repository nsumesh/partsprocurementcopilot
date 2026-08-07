# Parts Procurement Copilot — Implementation Plan

## Context

Greenfield build of a fleet operator procurement tool. All architectural decisions confirmed in `design-decisions.md` (ground truth). The system accepts a VIN + NL parts request, runs hybrid retrieval + rerank + fitment pipeline, and streams results via SSE. Two Railway services (API + frontend) backed by Supabase.

Urgency toggle: Standard = `claude-sonnet-4-6` for intent + fitment. Urgent = `claude-haiku-4-5` for both — same pipeline, lower latency.

---

## Repo Layout

```
/
├── .env.example
├── railway.toml
├── migrations/001_initial.sql
├── backend/
│   ├── .python-version
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db/supabase.py, sqlite_fts.py
│   │   ├── api/search.py, orders.py, vin.py
│   │   ├── pipeline/intent.py, embed.py, retrieve.py, rerank.py, fitment.py, stream.py
│   │   ├── schemas/parts.py, search.py, orders.py
│   │   └── vin/decoder.py
│   └── ingestion/
│       ├── scraper.py, aftermarket.py, normalizer.py, embedder.py
│       ├── loader.py, vin_seeds.py, eval_runner.py
└── frontend/
    ├── package.json, tsconfig.json, vite.config.ts, tailwind.config.ts, index.html
    └── src/
        ├── types/index.ts
        ├── api/client.ts, search.ts, orders.ts, vin.ts
        ├── components/SearchBar, PartCard, PartDetail, OrderConfirm, OrderHistory
        └── pages/SearchPage.tsx, OrdersPage.tsx, App.tsx, main.tsx
```

---

## Ingestion Timing

Data flows in two stages:

1. **VIN seeds** — 5 eval VINs hardcoded in `ingestion/vin_seeds.py`, seeded into `vin_cache`. Run this first so VIN lookups work without hitting NHTSA. Loader calls it automatically.
2. **Parts** — OE parts scraped from finditparts.com (`scraper.py`), aftermarket data LLM-generated (`aftermarket.py`), both normalised → embedded → upserted to Supabase and SQLite FTS by `loader.py`. Must run before search pipeline returns results.

> **No parts in DB = empty search results, not an error.** The API boots and FTS initialises fine against an empty table; search just returns `[DONE]` immediately. Run ingestion once after CP-2 to unblock end-to-end testing.

---

## Implementation Batches + Checkpoints

**Batch 1 (parallel):** `migrations/001_initial.sql` + `backend/.python-version` + `backend/pyproject.toml` + `.env.example` ✅

### CP-1: Schema applied to Supabase ✅
```sql
-- Run migrations/001_initial.sql in Supabase SQL Editor
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
-- Expected: parts, orders, vin_cache
SELECT proname FROM pg_proc WHERE proname = 'match_parts';
-- Expected: match_parts
```

---

**Batch 2 (parallel):** `backend/app/config.py` + `backend/app/main.py` + all three `backend/app/schemas/` files ✅

**Batch 3 (parallel):** `backend/app/db/supabase.py` + `backend/app/db/sqlite_fts.py` + `backend/app/vin/decoder.py` ✅

**Batch 4 (parallel):** All six `backend/app/pipeline/` modules (intent, embed, retrieve, rerank, fitment, stream) ✅

**Batch 5 (parallel):** `backend/app/api/vin.py` + `backend/app/api/orders.py` + `backend/app/api/search.py` ✅

### CP-2: API boots + VIN endpoint live ✅
```bash
cd backend
cp ../.env.example .env   # fill in real keys
uv sync
uv run uvicorn app.main:app --reload
# Expected: "Application startup complete" with no errors
# FTS rebuilds to empty index (no parts yet — that's OK)

curl http://localhost:8000/vin/1XKAD49X1EJ391052
# Expected: 200 VINSpec from NHTSA, or 422 if NHTSA down
```

### CP-3: Ingest data ✅
```bash
cd backend
uv run python -m ingestion.loader
# Expected output:
#   Ingestion complete
#     OE parts:          N
#     Aftermarket parts: N
#     Deduplicated:      N
#     Time taken:        Xs
# Parts now in Supabase + SQLite FTS rebuilt + 5 VINs in vin_cache
```
Verify in Supabase dashboard: `SELECT COUNT(*) FROM parts` > 0.

### CP-4: Search pipeline returns results ✅
```bash
curl -N -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"vin":"1XKAD49X1EJ391052","query":"oil filter","urgency":"standard"}'
# Expected: stream of SSE events ending with data: {"type":"done"}
# Each part event: {"type":"part","index":0,"part":{...},"fitment":{...}}
```

---

**Batch 6 (parallel):** `ingestion/vin_seeds.py` + `ingestion/scraper.py` + `ingestion/aftermarket.py` + `ingestion/normalizer.py` + `ingestion/embedder.py` ✅

**Batch 7 (sequential):** `ingestion/loader.py` → `ingestion/eval_runner.py` ✅

### CP-5: Eval passes ✅ (5/5 after prompt + fitment year_range fixes)
```bash
cd backend
uv run python -m ingestion.eval_runner
# Expected: 5/5 queries pass
# correct_part_found=True, rank_position ≤ 3 for all golden queries
# VIN 4V4NC9EH9EN157361 triggers clarify event (ambiguous query)
```

---

**Batch 8 (parallel):** Frontend scaffold + `src/types/index.ts` + all `src/api/` files

**Batch 9 (parallel):** All five `src/components/` files

**Batch 10 (parallel):** `pages/SearchPage.tsx` + `pages/OrdersPage.tsx` + `App.tsx` + `main.tsx` ✅

### CP-6: Frontend golden path
```bash
cd frontend && npm install && npm run dev
# Open http://localhost:5173
# Golden path:
#   1. Enter eval VIN → vehicle confirmation shown below input
#   2. Enter NL query → submit → part cards stream in one by one
#   3. Click card → detail panel with fitment reasoning + vendor links
#   4. Click "Order" → quantity modal → confirm
#   5. Navigate to /orders → order appears in history
# Check DevTools Network: /search response is text/event-stream, events arrive incrementally
```

---

**Batch 11 (parallel):** `backend/Dockerfile` + `frontend/Dockerfile` + `railway.toml`

---

## Key Design Decisions (from design-decisions.md)

- **Scraping:** Browserbase + Playwright → finditparts.com
- **Aftermarket data:** LLM-generated synthetic CSV (claude-sonnet-4-6)
- **Retrieval:** SQLite FTS5 (BM25) + Supabase pgvector (ANN), merged via RRF (k=60)
- **Async:** FastAPI + asyncio, SSE streaming, no Celery/Redis
- **Embeddings:** Cohere `embed-english-v3.0` (1024-dim)
- **Reranker:** Cohere `rerank-english-v3.0`
- **Intent + fitment:** claude-sonnet-4-6 (standard) or claude-haiku-4-5 (urgent), temperature=0
- **VIN:** NHTSA VPIC primary, local fallback for 5 eval VINs
- **DB:** Supabase Postgres + pgvector; SQLite FTS rebuilt from Supabase on startup
- **Deployment:** Railway (API + frontend), Supabase (DB)
- **Auth:** None (single-user)
- **Orders:** Intent records only, no payment

---

## Database Schema (migrations/001_initial.sql)

Three tables: `parts` (id, part_number, name, description, category, source, brand, price_usd, fit_notes JSONB, attributes JSONB, vendor_urls JSONB, embedding vector(1024)), `orders` (id, part_id→parts, part_number, part_name, quantity, vin, query, urgency, created_at), `vin_cache` (vin PK, make, model, year, engine, gvwr, raw_vpic JSONB). IVFFlat index on parts.embedding. RLS permissive policies on all tables.

---

## AI Pipeline Flow (api/search.py)

```
decode_vin → parse_intent → [if ambiguous: sse_clarify + return]
→ embed_query → retrieve (pgvector + BM25 parallel + RRF)
→ rerank → for each part: assign_fitment → sse_part
→ sse_done
```

---

## Code Explainability

After **every batch** is approved, append entries to `code-explainability.md` at the repo root before moving to the next batch. One entry per file: path, what it does (2–4 sentences), external services called, what calls it. This applies to both v1.0 batches and all vendor outreach feature batches.

---

## Verification

```bash
cd backend && uv run python -m ingestion.loader       # ingestion report
cd backend && uv run python -m ingestion.eval_runner  # 5/5 golden queries
cd backend && uv run uvicorn app.main:app --reload    # API dev server
cd frontend && npm run dev                            # frontend dev server
```

---

## Deployment (Railway) — Completed 2026-04-26

Two Railway services deployed from this monorepo. Each service has its Root Directory set in the Railway dashboard so builds use the correct Dockerfile.

| Service | Root Directory | Public URL |
|---------|---------------|------------|
| api | `backend/` | https://api-production-4fff.up.railway.app |
| frontend | `frontend/` | https://frontend-production-bc15.up.railway.app |

**Key lessons learned during deployment:**

- `[[services]]` blocks in `railway.toml` are not valid Railway config — replaced with per-directory `railway.toml` files using only `[build]` and `[deploy]` sections.
- Railway assigns a dynamic `$PORT` — both services must bind to it. Backend uses shell-form CMD with `${PORT:-8000}`; frontend uses `envsubst` to inject `$PORT` into the nginx config template at startup.
- `VITE_API_BASE_URL` is a Vite build-time variable baked into the JS bundle. It must be set as a Railway environment variable **before** the frontend build runs, not after.
- `railway up` from a subdirectory still uploads the full git repo root. GitHub-connected deploys with Root Directory configured per service is the correct monorepo approach.

See `deployment-steps.md` for the full step-by-step guide.

---

## Feature Addition: Vendor Outreach Agent

**Status:** Batch 1 complete. Batches 2–11 pending.

Extends the parts procurement flow with an AI-driven vendor outreach loop. Operator selects a vendor, reviews a Haiku-generated outreach email, confirms send, then watches the job board as the vendor "responds" (simulated by Haiku), the response is parsed, follow-up generated if fields are missing, composite score computed, and operator accepts or rejects.

**New env vars required (frontend):** `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`

---

### Batch 1 — Database Migration ✅

**`migrations/002_vendor_outreach.sql`** — applied in Supabase directly.

Four new tables: `vendors`, `vendor_parts`, `procurement_jobs`, `procurement_events`.

```sql
-- Indexes added:
CREATE INDEX ON procurement_jobs(status, respond_at);         -- worker poll
CREATE INDEX ON procurement_events(job_id, created_at DESC);  -- last-action lookup
-- RLS permissive policies on all 4 tables (same pattern as 001)
-- Supabase Realtime: enable on procurement_jobs via Dashboard → Database → Replication
```

---

### Batch 2 — Backend Schemas

**`backend/app/schemas/procurement.py`** (new)

Pydantic models: `Vendor`, `VendorPart`, `JobStatus` (Literal union), `ProcurementJobCreate`, `ProcurementJob`, `ProcurementEvent`. Same patterns as `schemas/parts.py` and `schemas/orders.py` — BaseModel, Literal/Enum for constrained fields, `| None` optionals.

---

### Batch 3 — DB Layer

**`backend/app/db/supabase.py`** (extend)

Nine new async functions using same `.table().select/insert/update().execute()` pattern:

| Function | Description |
|----------|-------------|
| `fetch_vendors_for_part(client, part_id)` | JOIN vendor_parts + vendors |
| `insert_procurement_job(client, job: dict)` | Returns new job dict |
| `update_procurement_job(client, job_id, fields: dict)` | Partial update |
| `fetch_procurement_jobs(client)` | All jobs with vendor join, ORDER BY created_at DESC |
| `fetch_procurement_job(client, job_id)` | Single job or None |
| `fetch_pending_simulations(client)` | status IN ('outreach_sent','follow_up_sent') AND respond_at <= now() |
| `fetch_confirmed_unranked(client)` | status='confirmed' AND ranking_score IS NULL |
| `insert_procurement_event(client, event: dict)` | Append to event log |
| `fetch_job_events(client, job_id)` | All events for a job |

---

### Batch 4 — Ingestion (parallel)

**`backend/ingestion/vendor_seeder.py`** (new)

- `seed_vendors(client)` — upserts 10 vendors from vendors.md hardcoded dict, on_conflict="name"
- `seed_vendor_parts(client)` — fetches all parts + vendors, generates vendor_parts rows:
  - Each part gets 2–5 randomly sampled vendors
  - `delivery_estimate`: random from pool `["2 hours", "Next business day", "3-5 business days", "1 week", "8-10 days", "2 weeks", "~20 days"]`
  - `delivery_hours`: hardcoded int map per estimate string
  - `list_price`: `part.price_usd * random.uniform(0.85, 1.25)`
  - `in_stock`: True for 80% of rows
  - upsert on_conflict="vendor_id,part_id"

**`backend/ingestion/loader.py`** (extend)

Add step 10 after existing seed_vins:
```python
from ingestion.vendor_seeder import seed_vendors, seed_vendor_parts
await seed_vendors(supabase)
await seed_vendor_parts(supabase)
```

---

### CP-V1: Vendor Ingestion
```bash
cd backend && uv run python -m ingestion.vendor_seeder
# Expected: "Seeded 10 vendors, N vendor_parts rows"

# Verify in Supabase SQL editor:
SELECT COUNT(*) FROM vendors;          -- Expected: 10
SELECT COUNT(*) FROM vendor_parts;     -- Expected: several hundred (2-5 per part)
SELECT v.name, vp.delivery_estimate, vp.delivery_hours, vp.list_price
FROM vendor_parts vp JOIN vendors v ON v.id = vp.vendor_id LIMIT 10;
-- Expected: mixed delivery_estimate strings, delivery_hours populated, prices near part.price_usd
```

---

### Batch 5 — Agent Modules (all parallel)

All use `claude-haiku-4-5-20251001`, `temperature=0`, same markdown-fence-strip + `json.loads` pattern as `pipeline/intent.py`. All accept `client: AsyncAnthropic` as parameter.

**`backend/app/agents/__init__.py`** (new, empty)

**`backend/app/agents/email_generator.py`**
`generate_outreach_email(part, vendor, vin_spec, urgency, deadline, client) -> str`
Returns plain email text. System prompt: professional fleet procurement agent requesting part availability, price, and delivery timeline.

**`backend/app/agents/response_simulator.py`**
`simulate_vendor_response(job, vendor, vendor_part, client) -> str`
- Tone by vendor type: OEM Manufacturer=formal, Aftermarket Distributor=professional casual, Truck Stop=terse
- `P(field_missing) = (1 - vendor.response_rate) * 0.6` per field — prompt instructs Haiku which fields to omit
- Fields that can be omitted: availability_status, unit_price, quantity_available, estimated_delivery_date
- Returns raw email text in vendor voice

**`backend/app/agents/email_parser.py`**
`parse_vendor_response(response_text, client) -> dict`
JSON output: `{availability_status, unit_price, quantity_available, estimated_delivery_date, missing_fields: []}`. Null for absent fields.

**`backend/app/agents/followup_generator.py`**
`generate_followup_email(original_email, response_text, missing_fields, vendor, client) -> str`
Returns plain follow-up email referencing specific missing fields by name.

**`backend/app/agents/ranker.py`**
`compute_ranking_score(unit_price, delivery_hours, response_rate, max_catalog_price=500.0) -> float`
Pure Python. `score = 0.4*(1-price/max) + 0.4*(1-hours/480) + 0.2*response_rate`. Clamp output to [0, 1].

---

### CP-V2: Agent Module Smoke Tests
```bash
cd backend
# Start a quick Python REPL against live env
uv run python - <<'EOF'
import asyncio, os
from dotenv import load_dotenv
load_dotenv()
from anthropic import AsyncAnthropic
from app.agents.email_generator import generate_outreach_email
from app.agents.response_simulator import simulate_vendor_response
from app.agents.email_parser import parse_vendor_response
from app.agents.followup_generator import generate_followup_email
from app.agents.ranker import compute_ranking_score

client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

async def main():
    # Minimal stubs
    part = type("P", (), {"name": "Oil Filter", "part_number": "LF9009", "category": "Filters", "price_usd": 45.0})()
    vendor = type("V", (), {"name": "FleetPride", "email": "parts@fleetpride.com", "type": "Aftermarket Distributor", "response_rate": 0.85})()
    vin_spec = type("V", (), {"make": "Kenworth", "model": "T680", "year": 2014, "engine": "Paccar MX-13"})()

    email = await generate_outreach_email(part, vendor, vin_spec, "urgent", None, client)
    print("=== OUTREACH EMAIL ===\n", email[:300])

    job = type("J", (), {"outreach_email": email, "part_name": part.name, "vin": "1XKAD49X1EJ391052"})()
    vp = type("VP", (), {"delivery_estimate": "3-5 business days", "list_price": 47.0})()
    response = await simulate_vendor_response(job, vendor, vp, client)
    print("=== VENDOR RESPONSE ===\n", response[:300])

    parsed = await parse_vendor_response(response, client)
    print("=== PARSED FIELDS ===\n", parsed)

    if parsed.get("missing_fields"):
        followup = await generate_followup_email(email, response, parsed["missing_fields"], vendor, client)
        print("=== FOLLOW-UP EMAIL ===\n", followup[:300])

    score = compute_ranking_score(47.0, 96, 0.85)
    print("=== RANKING SCORE ===", score)   # Expected: ~0.62–0.72

asyncio.run(main())
EOF
# All five sections should print without error
# parsed dict should contain availability_status, unit_price, quantity_available, estimated_delivery_date
# missing_fields list should be [] or contain field names (not crash)
```

---

### Batch 6 — Worker Loop

**`backend/app/workers/__init__.py`** (new, empty)

**`backend/app/workers/job_processor.py`** (new)

`async def job_processor_loop(app_state)` — infinite loop with `asyncio.sleep(30)` each cycle.

Each cycle:
1. `fetch_pending_simulations()` → for each job:
   - `simulate_vendor_response()` → store in `response_email`
   - `parse_vendor_response()` → store parsed fields
   - If `missing_fields` → status=`follow_up_required`, generate + store `follow_up_email`
   - Else → status=`confirmed`
   - Write `procurement_events` rows for each transition
2. `fetch_confirmed_unranked()` → for each:
   - `compute_ranking_score()` → update `ranking_score`
   - status=`ranked`, write event row

`respond_at` computation (set when job transitions to `outreach_sent` or `follow_up_sent`):
- `response_rate >= 0.85` → `now() + 3 min`
- `0.70 <= response_rate < 0.85` → `now() + random(10, 15) min`
- `response_rate < 0.70` → `now() + 20 min`

Error handling: per-job `try/except`, failed jobs log error in event metadata, stay in current status (no silent swallowing).

---

### CP-V3: Worker Loop (requires Batch 8 — main.py wired up)
```bash
# Start the API locally with worker enabled
cd backend && uv run uvicorn app.main:app --reload

# In a second terminal — insert a test job directly in Supabase SQL editor,
# set respond_at to now() - 1 second so the worker fires immediately:
INSERT INTO procurement_jobs (
  part_id, vendor_id, part_number, part_name, vin, query, urgency,
  status, respond_at, outreach_email, created_at, updated_at
) VALUES (
  '<any_valid_part_uuid>', '<any_valid_vendor_uuid>',
  'TEST-001', 'Test Oil Filter', '1XKAD49X1EJ391052', 'oil filter', 'standard',
  'outreach_sent', now() - interval '1 second',
  'Hi, please confirm availability of TEST-001.',
  now(), now()
);

# Within 30s, verify the worker fired:
SELECT id, status, parsed_availability, parsed_unit_price, follow_up_email, ranking_score
FROM procurement_jobs WHERE part_number = 'TEST-001';
-- Expected: status = 'confirmed' or 'follow_up_required'
-- parsed_unit_price populated (or null if follow_up_required)

SELECT from_status, to_status, actor, created_at
FROM procurement_events WHERE job_id = '<job_id_from_above>'
ORDER BY created_at;
-- Expected: at least one row showing outreach_sent → confirmed (or → follow_up_required)
```

---

### Batch 7 — API Routes (parallel)

**`backend/app/api/vendors.py`** (new)
`GET /vendors/part/{part_id}` → `list[VendorPart]`

**`backend/app/api/procurement.py`** (new)

| Method | Path | Action |
|--------|------|--------|
| POST | `/procurement/jobs` | Create job + generate outreach email → status=`created` |
| GET | `/procurement/jobs` | List all jobs with vendor info |
| GET | `/procurement/jobs/{id}` | Single job + events list |
| POST | `/procurement/jobs/{id}/send` | Confirm outreach → status=`outreach_sent` + set `respond_at` |
| POST | `/procurement/jobs/{id}/followup` | Confirm follow-up → status=`follow_up_sent` + set `respond_at` |
| POST | `/procurement/jobs/{id}/accept` | → status=`accepted` |
| POST | `/procurement/jobs/{id}/reject` | → status=`rejected` |

Each action writes a `procurement_events` row. All routes use `request.app.state.supabase`.

---

### CP-V4: API Routes
```bash
cd backend && uv run uvicorn app.main:app --reload

# 1. Vendor list for a part
PART_ID=$(curl -s "http://localhost:8000/search" ... | jq -r '.part.id' | head -1)
# Or grab any UUID from: SELECT id FROM parts LIMIT 1 in Supabase
curl http://localhost:8000/vendors/part/$PART_ID
# Expected: JSON array with vendor name, ETA, price, in_stock

# 2. Create a procurement job
JOB=$(curl -s -X POST http://localhost:8000/procurement/jobs \
  -H "Content-Type: application/json" \
  -d "{\"part_id\":\"$PART_ID\",\"vendor_id\":\"<vendor_uuid>\",
       \"part_number\":\"LF9009\",\"part_name\":\"Oil Filter\",
       \"vin\":\"1XKAD49X1EJ391052\",\"query\":\"oil filter\",\"urgency\":\"standard\"}")
echo $JOB | jq '{id, status, outreach_email: .outreach_email[:80]}'
# Expected: status="created", outreach_email non-empty

JOB_ID=$(echo $JOB | jq -r '.id')

# 3. Send outreach
curl -s -X POST http://localhost:8000/procurement/jobs/$JOB_ID/send | jq '{status, respond_at}'
# Expected: status="outreach_sent", respond_at = 3–20 min from now

# 4. List all jobs
curl -s http://localhost:8000/procurement/jobs | jq '[.[] | {id, status, part_name}]'
# Expected: array including the job just created

# 5. Accept/reject (set up a ranked job first, or test independently)
curl -s -X POST http://localhost:8000/procurement/jobs/$JOB_ID/accept | jq '.status'
# Expected: "accepted"
```

---

### Batch 8 — Backend Integration

**`backend/app/main.py`** (edit)

1. Import + include `vendors.router` and `procurement.router`
2. Start worker in lifespan:
```python
from app.workers.job_processor import job_processor_loop
task = asyncio.create_task(job_processor_loop(app.state))
yield
task.cancel()
```

Verification:
```bash
curl /vendors/part/{any_part_id}        # → list of VendorPart
curl -X POST /procurement/jobs {...}    # → job with status=created, outreach_email populated
curl -X POST /procurement/jobs/{id}/send  # → status=outreach_sent, respond_at set
# Wait ≤ 30s after respond_at → GET /procurement/jobs/{id} shows confirmed or follow_up_required
```

---

### Batch 9 — Frontend Types + API (parallel)

**`frontend/src/types/index.ts`** (extend)
Add: `Vendor`, `VendorPart`, `JobStatus` union, `ProcurementJob`, `ProcurementJobCreate`.

**`frontend/src/api/vendors.ts`** (new)
`getVendorsForPart(part_id)` using `apiGet<VendorPart[]>` from client.ts.

**`frontend/src/api/procurement.ts`** (new)
`createProcurementJob`, `getProcurementJobs`, `getProcurementJob`, `sendOutreach`, `sendFollowup`, `acceptJob`, `rejectJob` — all using `apiGet`/`apiPost`.

**`frontend/package.json`** (edit)
Add `"@supabase/supabase-js": "^2.0.0"`.

---

### Batch 10 — New Components (all parallel)

**`frontend/src/components/VendorSelector.tsx`** (new)
Modal (same overlay + animate-fade-up pattern as OrderConfirm).
- Props: `{ part, urgency, urgencyDeadline, onSelect(vendorPart, deadline), onClose }`
- Fetches vendors on mount via `getVendorsForPart`
- Cards: vendor name, type badge, response rate, ETA, list price
- If urgency=urgent: datetime-local input pre-filled from `urgencyDeadline`; highlight vendors whose `delivery_hours` fits deadline
- Single vendor click → `onSelect(vendorPart, deadline)`

**`frontend/src/components/OutreachConfirm.tsx`** (new)
Modal showing generated outreach email.
- Props: `{ job, onConfirm, onCancel }`
- Editable textarea pre-filled with `job.outreach_email`
- "Send Outreach" button → `sendOutreach(job.id)` → `onConfirm()`

**`frontend/src/components/VendorOutreachPanel.tsx`** (new)
Right-side panel (animate-slide-in-right, same as PartDetail).
- Props: `{ job, onClose, onJobUpdate }`
- Sections: status header + elapsed time, outreach email (collapsible), vendor response (when received), parsed fields table (missing fields in amber), follow-up editor when status=`follow_up_required`, ranking score breakdown when ranked, Accept/Reject buttons when ranked

**`frontend/src/components/ProcurementJobRow.tsx`** (new)
Table row. Columns: Part Name | Vendor | Status badge | Time elapsed | Last action.
Status colours: `outreach_sent`/`awaiting_response`=yellow pulse, `follow_up_required`=amber, `confirmed`/`ranked`=green, `accepted`=emerald, `rejected`=red.

---

### Batch 11 — Frontend Integration

**`frontend/src/pages/ProcurementBoard.tsx`** (new)
Route `/procurement`. Sticky header, full-width table of `ProcurementJobRow`. Supabase Realtime subscription on `procurement_jobs` updates matching row in state without page refresh. Click row → `VendorOutreachPanel` slide-in.

**`frontend/src/components/PartDetail.tsx`** (edit)
Add `onProcure: () => void` prop. Add "Create Procurement Request" as primary orange button alongside existing "Order This Part".

**`frontend/src/pages/ResultsPage.tsx`** (edit)
New state: `procureTarget`, `selectedVendorPart`, `procurementJob`.
Flow: `onProcure` → VendorSelector → `createProcurementJob` → OutreachConfirm → `sendOutreach` → toast + navigate to `/procurement`.
Read `urgency_deadline` from `location.state`.

**`frontend/src/pages/SearchPage.tsx`** (edit)
Pass `urgency_deadline` in navigate state: `navigate("/results", { state: { vin, query, urgency, urgency_deadline } })`.

**`frontend/src/components/SearchBar.tsx`** (edit)
When urgency=`urgent`: render datetime-local input below toggle (min = now+2h). Extend `onSearch` signature to include `urgency_deadline: string | null`.

**`frontend/src/App.tsx`** (edit)
Add `<Route path="/procurement" element={<ProcurementBoard />} />`.

---

### Vendor Outreach Verification Checklist

```bash
# 1. Seed vendors
cd backend && uv run python -m ingestion.vendor_seeder
# Expected: 10 vendors, N vendor_parts rows printed

# 2. Vendor list for a part
curl /vendors/part/{part_id}
# Expected: list with ETA, price, response rate

# 3. Create job
curl -X POST /procurement/jobs -d '{part_id, vendor_id, vin, query, urgency}'
# Expected: job in status=created, outreach_email populated

# 4. Send outreach
curl -X POST /procurement/jobs/{id}/send
# Expected: status=outreach_sent, respond_at = 3–20 min from now

# 5. Worker fires (wait ≤ 30s after respond_at)
curl /procurement/jobs/{id}
# Expected: status=confirmed or follow_up_required, parsed fields present

# 6. Events log
curl /procurement/jobs/{id}/events
# Expected: transition rows with actor, timestamps

# 7. Live board
# Open /procurement → update job status via API → row updates without refresh

# 8. Accept/reject
curl -X POST /procurement/jobs/{id}/accept
# Expected: status=accepted
```
