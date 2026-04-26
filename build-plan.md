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

After each batch is approved in the IDE, append entries to `code-explainability.md` at the repo root. One entry per file: path, what it does (2–4 sentences), external services called, what calls it.

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
