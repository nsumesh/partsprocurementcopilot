# System Architecture — HeaviAI Procurement CoPilot

**Status:** v1.0 — baseline before feature addition  
**Date:** 2026-04-26  
**Live:** api `https://api-production-4fff.up.railway.app` · frontend `https://frontend-production-bc15.up.railway.app`

---

## Overview

A two-service web application that accepts a vehicle VIN and a natural language parts request, runs a hybrid AI retrieval and fitment pipeline, and streams ranked results to the operator in real time. No payment processing. Orders are intent records only.

```
Browser
  │
  ├── GET  /vin/{vin}          VIN decode + vehicle confirmation
  ├── POST /search             SSE stream of ranked + fitment-assessed parts
  ├── POST /orders             Place an order (intent record)
  └── GET  /orders             Fetch order history
         │
    FastAPI (Railway)
         │
    ┌────┴─────────────────────────────────────┐
    │  decode_vin → parse_intent → embed_query  │
    │  → retrieve (pgvector + BM25 + RRF)       │
    │  → rerank → assign_fitment (per part)     │
    │  → SSE stream                             │
    └────┬──────────┬───────────────────────────┘
         │          │
    Supabase     SQLite FTS5
    (pgvector,   (BM25 index,
     orders,      in-container
     vin_cache)   file)
         │
    ┌────┴──────────────────────┐
    │  Anthropic Claude          │  intent parsing + fitment scoring
    │  Cohere                    │  embeddings + rerank
    │  NHTSA VPIC API            │  VIN decode (cached)
    └───────────────────────────┘
```

---

## Services

### api (backend)
- **Runtime:** Python 3.12, FastAPI, uvicorn, uv
- **Host:** Railway, built from `backend/Dockerfile`
- **Port:** `$PORT` (Railway-assigned dynamic)
- **Startup:** async lifespan — initialises Supabase client singleton, rebuilds SQLite FTS index from Supabase if missing
- **CORS:** `allow_origins=["*"]` (single-operator tool, no auth)

### frontend
- **Runtime:** React 18, TypeScript, Vite → nginx:alpine
- **Host:** Railway, built from `frontend/Dockerfile`
- **Port:** `$PORT` (injected into nginx config via `envsubst` at container startup)
- **Build-time config:** `VITE_API_BASE_URL` baked into JS bundle at Docker build time

---

## Database — Supabase (PostgreSQL + pgvector)

### `parts`
Canonical parts catalog. OE and aftermarket parts share the table, distinguished by `source`.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | `gen_random_uuid()` |
| `part_number` | TEXT | Manufacturer part number |
| `name` | TEXT | Display name |
| `description` | TEXT | Free-text description |
| `category` | TEXT | e.g. "Filters", "Brakes" |
| `source` | TEXT | `OE` or `aftermarket` |
| `brand` | TEXT | |
| `price_usd` | NUMERIC(10,2) | Nullable |
| `fit_notes` | JSONB | `{make, model, engine, year_range, notes}` |
| `attributes` | JSONB | Physical specs (dimensions, weight, etc.) |
| `vendor_urls` | JSONB | `[{vendor, url, price}]` |
| `embedding` | vector(1024) | Cohere embed-english-v3.0 |
| `created_at` | TIMESTAMPTZ | |

Unique constraint: `(part_number, source)`.  
Index: IVFFlat cosine on `embedding` (lists=100).  
SQL function: `match_parts(query_embedding, match_count)` — `ORDER BY embedding <=> query_embedding LIMIT match_count`.

### `orders`
Intent records. No payment, no external fulfilment integration.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `part_id` | UUID → parts | `ON DELETE SET NULL` |
| `part_number` | TEXT | Denormalised for display |
| `part_name` | TEXT | Denormalised for display |
| `quantity` | INTEGER | `CHECK > 0` |
| `vin` | TEXT | Vehicle the order was placed for |
| `query` | TEXT | Original NL query |
| `urgency` | TEXT | `standard` or `urgent` |
| `created_at` | TIMESTAMPTZ | |

### `vin_cache`
Decoded VIN records. Caches NHTSA VPIC responses to avoid repeat API calls.

| Column | Type | Notes |
|--------|------|-------|
| `vin` | TEXT PK | 17-character VIN |
| `make` | TEXT | |
| `model` | TEXT | |
| `year` | INTEGER | |
| `engine` | TEXT | |
| `gvwr` | TEXT | |
| `raw_vpic` | JSONB | Full NHTSA response |
| `created_at` | TIMESTAMPTZ | |

RLS is enabled on all three tables with permissive `allow_all` policies (no auth layer).

---

## In-Container Storage — SQLite FTS5

A SQLite file (`fts_index.db`) lives inside the api container. It is rebuilt from Supabase on cold start if missing.

- **Virtual table:** FTS5 with porter tokenizer on `(part_number, name, description, category, brand)`
- **Lookup table:** `parts_lookup (rowid → part_id UUID)`
- **Query:** BM25 scoring via `bm25(fts_parts)`, returns `(part_id, score)` pairs
- **Thread safety:** `check_same_thread=False` — build is single-writer at startup, queries are read-only at request time via `run_in_executor`

The FTS index is ephemeral — it is not committed to git and not persisted across Railway deploys. Cold-start rebuild takes ~2–3 seconds for 170 parts.

---

## AI Pipeline (per search request)

All steps are sequential within a single async generator. The generator yields SSE events directly to the HTTP response.

```
1. decode_vin(vin)
   └── Check vin_cache → if miss: NHTSA VPIC API → upsert cache
   └── Returns VINSpec {make, model, year, engine, gvwr}

2. parse_intent(query, vin_spec, model)
   └── Claude: system prompt → JSON {part_category, attributes, clarifying_question, is_ambiguous}
   └── If is_ambiguous=true → yield sse_clarify → return early

3. embed_query(query)
   └── Cohere embed-english-v3.0, input_type="search_query"
   └── Returns 1024-dim float list

4. retrieve(query_text, query_embedding, top_k=10)
   └── Parallel via asyncio.gather:
       ├── pgvector: match_parts(embedding, 10) → [(part_id, distance)]
       └── SQLite BM25: fts.query(text, 10) → [(part_id, score)]
   └── RRF merge (k=60): score += 1/(60+rank) per list
   └── Returns top-10 part_ids by RRF score

5. fetch_parts_by_ids(candidate_ids)
   └── Single Supabase query → list[Part]

6. rerank(query, parts)
   └── Cohere rerank-english-v3.0
   └── Document = "{name} {description} {category}"
   └── Returns parts reordered by relevance score

7. for each part in reranked:
   └── assign_fitment(part, vin_spec, model)
       ├── Step 1 — Structured match: compare fit_notes {make, model, engine} to vin_spec
       │   └── Full match → HIGH confidence, skip LLM
       └── Step 2 — LLM fallback (partial/missing fit_notes):
           └── Claude: fitment expert prompt → JSON {confidence, reasoning}
   └── yield sse_part(index, part, fitment_result)

8. yield sse_done()
```

### Model selection by urgency

| Urgency | Intent model | Fitment model | Characteristic |
|---------|-------------|---------------|----------------|
| `standard` | `claude-sonnet-4-6` | `claude-sonnet-4-6` | Higher accuracy |
| `urgent` | `claude-haiku-4-5-20251001` | `claude-haiku-4-5-20251001` | Lower latency |

Same pipeline steps for both — only the model swaps.

---

## API Routes

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check — returns `{"status":"ok"}` |
| `GET` | `/vin/{vin}` | Decode VIN → `VINSpec` or 422 |
| `POST` | `/search` | Run pipeline → `text/event-stream` SSE |
| `POST` | `/orders` | Create order → `Order` |
| `GET` | `/orders` | List all orders → `Order[]` |

### SSE event types (`POST /search`)

| Type | Payload | Meaning |
|------|---------|---------|
| `part` | `{type, part, fitment, rank}` | One result ready |
| `clarify` | `{type, question}` | Query too ambiguous, needs refinement |
| `done` | `{type}` | Pipeline complete |
| `error` | `{type, message}` | Pipeline failed |

Headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no` (prevents Railway/nginx buffering).

---

## Frontend Architecture

### Screen flow
```
/  (SearchPage)
   └── VIN input (blur → GET /vin/{vin} → vehicle confirmation)
   └── Query textarea
   └── Urgency toggle (Standard / Urgent)
   └── Find Parts → navigate("/results", { state: {vin, query, urgency} })

/results  (ResultsPage)
   └── On mount → POST /search → SSE stream
   └── PartCard per result (fade-in as each arrives)
   └── FilterPanel sidebar (client-side, applied to already-streamed results[])
   └── Click card → PartDetail panel (slide-in right)
   └── Order → OrderConfirm modal → POST /orders → navigate("/orders")

/orders  (OrdersPage)
   └── On mount → GET /orders
   └── OrderHistory table
```

### State management
No global state. Each page owns its state. `ResultsPage` is the main state owner:
- `results: SearchResultPart[]` — appended as SSE `part` events arrive
- `isStreaming: boolean`
- `clarifyQuestion: string | null`
- `filters: FilterState` — client-side filter values
- `selectedResult` / `confirmTarget` — panel/modal visibility

### Client-side filtering
Filters applied in `applyFilters()` against the in-memory `results[]` array. No additional API calls on filter change. Covers: source (OEM/Aftermarket), fitment confidence, price range (min/max), year range (overlaps part's `fit_notes.year_range`). Parts with no `year_range` pass all year filters (treated as universally applicable).

---

## Ingestion Pipeline (offline, run locally)

Not deployed on Railway. Run once to populate the Supabase catalog.

```
scraper.py         → scrape OE parts from finditparts.com via Browserbase + Playwright
aftermarket.py     → generate aftermarket alternatives via Claude (CSV output)
normalizer.py      → normalize OE + aftermarket rows to canonical Part schema
embedder.py        → batch embed with Cohere (96 per batch, embed-english-v3.0, search_document)
loader.py          → orchestrate: scrape → generate → normalize → dedup → embed → upsert → build FTS → seed VINs
vin_seeds.py       → upsert 5 pre-decoded eval VINs to vin_cache
eval_runner.py     → run 5 golden queries, assert correct_part_found + confidence + clarify behaviour
```

**Catalog size:** 170 parts (OE + aftermarket), 26 VINs in cache.

---

## Deployment

```
GitHub (main branch)
   │
   ├── push → Railway builds backend/  → api service   (python:3.12-slim + uv)
   └── push → Railway builds frontend/ → frontend service (node:20-alpine build → nginx:alpine)
```

Each service has `railway.toml` in its directory declaring `builder = "DOCKERFILE"`. Root Directory is set per service in the Railway dashboard.

**Environment variables (api service):**
- `SUPABASE_URL`, `SUPABASE_KEY` (service role JWT)
- `ANTHROPIC_API_KEY`, `COHERE_API_KEY`

**Environment variables (frontend service):**
- `VITE_API_BASE_URL` — baked into JS bundle at build time; must be set before the build runs

---

## External Service Dependencies

| Service | Used by | Purpose |
|---------|---------|---------|
| Supabase | api | PostgreSQL + pgvector (parts, orders, vin_cache) |
| Anthropic Claude | api (pipeline) | Intent parsing, fitment scoring |
| Cohere | api (pipeline) | Text embeddings (1024-dim), reranking |
| NHTSA VPIC API | api (vin decoder) | VIN decode (free, public, cached) |
| Browserbase | ingestion only | Remote browser for Playwright scraping |
| Railway | both services | Container hosting, auto-deploy from GitHub |

---

## Known Limitations (v1.0)

- **No authentication.** Single-operator tool with permissive RLS. Adding auth requires Supabase Auth + JWT middleware.
- **FTS index is ephemeral.** Rebuilt from Supabase on each cold start (~2–3s). Large catalogs will increase cold-start time.
- **10-result cap.** `TOP_K=10` is hardcoded. No pagination.
- **Fitment is per-part sequential.** Each part makes one Claude call. 10 parts = 10 sequential LLM calls on the critical path.
- **No SSE heartbeat.** Network drops with no TCP RST will leave the client spinner hanging until OS keepalive timeout (~90s).
- **Orders are intent records only.** No integration with suppliers, ERP, or purchasing systems.
- **Ingestion is manual.** No scheduled re-scrape or catalog update mechanism.
