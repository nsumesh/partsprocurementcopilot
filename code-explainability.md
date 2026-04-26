# Code Explainability

Living document. Updated after each batch is approved. One entry per file: what it does, external services called, what calls it.

---

## migrations/001_initial.sql

**What it does:** Defines the Supabase Postgres schema. Creates three tables — `parts` (canonical OE + aftermarket catalog with pgvector embedding column), `orders` (intent records with no payment logic), and `vin_cache` (decoded VIN records). Also creates the `match_parts` SQL function used by the API for vector similarity search, an IVFFlat index on the embedding column, and permissive RLS policies for the single-user tool.

**External services:** Applied manually via Supabase SQL editor.

**What calls it:** Run once at project setup. The `ingestion/loader.py` pipeline writes to these tables. The FastAPI app reads from them at query time.

---

## backend/.python-version

**What it does:** Pins the Python version to 3.12 for the `backend/` directory. `uv` reads this file when creating the virtual environment, ensuring the correct interpreter is used locally and in CI.

**External services:** None.

**What calls it:** `uv` automatically reads it when running any `uv run` or `uv sync` command inside `backend/`.

---

## backend/pyproject.toml

**What it does:** Defines the backend Python project for `uv`. Declares all runtime dependencies (FastAPI, Supabase, Cohere, Anthropic, Playwright, Browserbase, httpx) and dev dependencies (pytest, pytest-asyncio). Also configures pytest to run in async mode and target the `tests/` directory.

**External services:** None directly — declares the packages that will be installed from PyPI.

**What calls it:** `uv sync` (install deps), `uv run` (run any backend command), Railway Dockerfile build.

---

## .env.example

**What it does:** Documents every environment variable the system requires. Covers Supabase credentials, Anthropic and Cohere API keys, Browserbase credentials for the ingestion scraper, and the frontend API base URL. Developers copy this to `.env` and fill in real values; `.env` is gitignored.

**External services:** None — this is documentation, not executable.

**What calls it:** Referenced by `backend/app/config.py` (pydantic-settings reads `.env`), and by the frontend Vite build (`VITE_API_BASE_URL`).

---

## backend/app/config.py

**What it does:** Defines the `Settings` class using `pydantic-settings`, reading all environment variables from `.env`. Exposes a `get_settings()` singleton via `@lru_cache` used as a FastAPI dependency throughout the app.

**External services:** None — reads local `.env` file.

**What calls it:** `app/main.py` (lifespan), `app/api/*.py` routes (via `Depends(get_settings)`), `app/vin/decoder.py`, ingestion scripts.

---

## backend/app/main.py

**What it does:** Creates the FastAPI application with CORS middleware and registers the three API routers (`/vin`, `/search`, `/orders`). On startup, initialises the Supabase client and the SQLite FTS index (rebuilding it from Supabase if the file is missing or empty).

**External services:** Supabase (via `db/supabase.py`), SQLite FTS (via `db/sqlite_fts.py`).

**What calls it:** `uvicorn app.main:app` — the entry point for the backend service.

---

## backend/app/schemas/parts.py

**What it does:** Defines the `Part` Pydantic model (canonical part record) and `FitmentResult` (confidence enum + reasoning string). `FitmentConfidence` is a str enum with four levels: High / Medium / Low / No Fitment.

**External services:** None.

**What calls it:** `schemas/search.py` imports `Part` and `FitmentResult`. Used as return types in all pipeline modules and API responses.

---

## backend/app/schemas/search.py

**What it does:** Defines request/response schemas for the search pipeline — `SearchRequest` (VIN + query + urgency), `VINSpec` (decoded vehicle attributes), `IntentResult` (parsed part category + attributes + ambiguity flag), and `SearchResultPart` (part + fitment + RRF score).

**External services:** None.

**What calls it:** `api/search.py`, `api/vin.py`, and all pipeline modules use these types as inputs and outputs.

---

## backend/app/schemas/orders.py

**What it does:** Defines `OrderCreate` (the POST body for placing an order) and `Order` (the stored record with `id` and `created_at`). Orders are intent records only — no payment fields.

**External services:** None.

**What calls it:** `api/orders.py` uses these as the request body and response type.

---

## backend/app/db/supabase.py

**What it does:** Wraps the `supabase-py` async client with typed helper functions for every DB operation the app needs: fetching and upserting parts, inserting and listing orders, reading/writing the VIN cache, and calling the `match_parts` RPC for vector similarity search.

**External services:** Supabase Postgres (all table reads/writes and the pgvector RPC).

**What calls it:** `app/main.py` (initialises the client), `pipeline/retrieve.py` (vector search), `pipeline/fitment.py` (part number validation), `api/orders.py`, `api/vin.py`, `db/sqlite_fts.py` (FTS rebuild), ingestion scripts.

---

## backend/app/db/sqlite_fts.py

**What it does:** Manages a local SQLite FTS5 index over the parts catalog. `build()` creates the virtual table with a porter tokeniser and a `parts_lookup` rowid→part_id mapping. `query()` runs a BM25 match and returns `(part_id, score)` pairs. `rebuild_if_missing()` is called on startup — if the file is absent or empty it fetches all parts from Supabase and rebuilds synchronously in a thread executor.

**External services:** SQLite (local file), Supabase (via `fetch_all_parts` for rebuild).

**What calls it:** `app/main.py` (startup rebuild), `pipeline/retrieve.py` (BM25 query leg), `ingestion/loader.py` (full rebuild after ingestion).

---

## backend/app/vin/decoder.py

**What it does:** Decodes a VIN into a `VINSpec` by first checking the `vin_cache` table in Supabase, then falling back to the NHTSA VPIC API. On a successful NHTSA response it upserts the decoded record to `vin_cache` for future cache hits. Returns `None` on network failure so the caller can return a 422.

**External services:** Supabase (`vin_cache` table), NHTSA VPIC REST API (`{nhtsa_api_base}/decodevinvalues/{vin}`).

**What calls it:** `api/vin.py` (GET /vin/{vin}), `api/search.py` (first step in the search pipeline).

---

## backend/app/pipeline/intent.py

**What it does:** Calls the Anthropic API with a structured system prompt to parse a technician's free-text query into `IntentResult` — a canonical part category, key-value attributes, and an ambiguity flag. If `is_ambiguous=True`, a `clarifying_question` is returned so the API can short-circuit the pipeline and ask the user to clarify.

**External services:** Anthropic API (`claude-sonnet-4-6` standard / `claude-haiku-4-5-20251001` urgent, temperature=0).

**What calls it:** `api/search.py` (step 2 of the pipeline, after VIN decode).

---

## backend/app/pipeline/embed.py

**What it does:** Embeds a single query string into a 1024-dimension float vector using Cohere's `embed-english-v3.0` model with `input_type="search_query"`. This vector is used for the pgvector ANN leg of hybrid retrieval.

**External services:** Cohere Embed API.

**What calls it:** `api/search.py` (step 3 of the pipeline, before `retrieve`).

---

## backend/app/pipeline/retrieve.py

**What it does:** Runs pgvector ANN (via Supabase `match_parts` RPC) and SQLite BM25 (via `FTSIndex.query`) concurrently with `asyncio.gather`, then merges the two ranked lists using Reciprocal Rank Fusion (k=60). Returns the top-N part IDs sorted by combined RRF score.

**External services:** Supabase pgvector RPC (`match_parts`), SQLite FTS (local file).

**What calls it:** `api/search.py` (step 4 of the pipeline).

---

## backend/app/pipeline/rerank.py

**What it does:** Takes the candidate `Part` list from retrieval and re-orders it using Cohere's `rerank-english-v3.0` model against the original query string. Returns parts in the order Cohere considers most relevant.

**External services:** Cohere Rerank API.

**What calls it:** `api/search.py` (step 5 of the pipeline, after parts are fetched from Supabase).

---

## backend/app/pipeline/fitment.py

**What it does:** Assigns a `FitmentResult` to each part. First tries a structured match against `part.fit_notes` (make/model/engine/year_range) — an exact match returns `HIGH` confidence immediately. If fit_notes are absent or don't fully match, falls back to the Anthropic API for an LLM-based confidence assessment.

**External services:** Anthropic API (`claude-sonnet-4-6` / `claude-haiku-4-5-20251001`, temperature=0) for LLM fallback only.

**What calls it:** `api/search.py` (step 6, called once per part in the stream loop).

---

## backend/app/pipeline/stream.py

**What it does:** Pure helper that serialises pipeline outputs into SSE-formatted strings. Four event types: `part` (part + fitment payload), `clarify` (question for the user), `done` (stream end), `error` (pipeline failure message).

**External services:** None.

**What calls it:** `api/search.py` yields the output of these functions directly into the `StreamingResponse`.

---

## backend/app/api/vin.py

**What it does:** Exposes `GET /vin/{vin}`. Delegates to `vin/decoder.py` and returns a `VINSpec`. Returns HTTP 422 if the VIN cannot be decoded (NHTSA unreachable and not in cache). Called by the frontend on VIN input blur to show vehicle confirmation.

**External services:** None directly — delegates to `vin/decoder.py`.

**What calls it:** Frontend `api/vin.ts` on input blur; used independently of the search pipeline.

---

## backend/app/api/orders.py

**What it does:** Exposes `POST /orders` (create intent record, returns `Order`) and `GET /orders` (list all orders newest-first). No payment logic — orders are purely intent records that the operator uses to track what to procure.

**External services:** Supabase (`orders` table via `db/supabase.py`).

**What calls it:** Frontend `api/orders.ts` — from `OrderConfirm` on confirm and `OrdersPage` on mount.

---

## backend/app/api/search.py

**What it does:** Exposes `POST /search` as a Server-Sent Events stream. Orchestrates the full pipeline — VIN decode → intent parse → embed → retrieve (pgvector + BM25 + RRF) → rerank → per-part fitment — yielding one SSE `part` event per result as it resolves. Short-circuits with a `clarify` event if the intent is ambiguous. Model selection (Sonnet vs Haiku) is driven by the `urgency` field on the request.

**External services:** Anthropic API (intent + fitment), Cohere (embed + rerank), Supabase pgvector, SQLite FTS — all via pipeline modules.

**What calls it:** Frontend `api/search.ts` via `fetch` + `ReadableStream`.

---

## backend/ingestion/vin_seeds.py

**What it does:** Hardcodes decoded VIN records for the 5 eval vehicles (Kenworth T680, Freightliner Cascadia, Volvo VNL, Peterbilt 386, Mack Pinnacle). `seed_vins()` upserts all 5 records to the `vin_cache` Supabase table so the eval queries never depend on a live NHTSA API call.

**External services:** Supabase (`vin_cache` table).

**What calls it:** `ingestion/loader.py` at the end of the ingestion pipeline (step 9/9).

---

## backend/ingestion/normalizer.py

**What it does:** Defines the `CanonicalPart` TypedDict (the shared in-memory schema for all parts before they hit Supabase). Exports `normalize_oe()` and `normalize_aftermarket()` — both map raw scraped/generated dicts into `CanonicalPart`, handling price parsing, category normalization, and JSON field coercion from CSV strings.

**External services:** None.

**What calls it:** `ingestion/loader.py` (normalizes both OE and aftermarket parts). `ingestion/embedder.py` imports `CanonicalPart` as the input type.

---

## backend/ingestion/embedder.py

**What it does:** Batches a list of `CanonicalPart` dicts into Cohere embed calls (batch size 96, `embed-english-v3.0`, `input_type="search_document"`). Builds document strings from `name + description + category + brand` and returns a parallel list of 1024-dim float embeddings.

**External services:** Cohere Embed API.

**What calls it:** `ingestion/loader.py` (step 5/9 — embeds all deduped parts before upsert).

---

## backend/ingestion/scraper.py

**What it does:** Scrapes OE parts from finditparts.com across 10 commercial truck part categories using Browserbase (remote Chrome) + Playwright. Loads the homepage once, then for each category fills `#searcher_s` and calls `form.requestSubmit()` via `page.evaluate()` (immune to modal overlay blocking). Two grids co-exist in the DOM: `.product_results_grid.loading` (skeleton, always present) and `.product_results_grid.loaded` (injected by AJAX when results arrive). Waits specifically for `.product_results_grid.loaded`, then selects `.product_results_grid.loaded .product_search_result` cards (scoped to avoid skeleton). Extracts all data in one `card.evaluate()` JS round-trip: `data-name`, `data-price`, `data-brand`, `data-category`, `data-category2`, description from `[itemprop="description"]`. Manufacturer part number is extracted by stripping the brand prefix from `data-name` (format: `"{BRAND} {PART_NUMBER}"`). Returns a list of raw dicts ready for `normalize_oe()`.

**External services:** Browserbase (remote browser sessions), finditparts.com (scraped), Playwright (browser automation).

**What calls it:** `ingestion/loader.py` (step 1/9).

---

## backend/ingestion/aftermarket.py

**What it does:** Takes the scraped OE parts, extracts unique categories, and calls `claude-sonnet-4-6` to generate 4 realistic aftermarket alternative SKUs per category (brand, price, fit_notes, attributes). Writes the results to a CSV file at `data/aftermarket.csv`. The generated data gives the retrieval pipeline aftermarket alternatives to surface alongside OE parts.

**External services:** Anthropic API (`claude-sonnet-4-6`).

**What calls it:** `ingestion/loader.py` (step 2/9, after OE scrape).

---

## backend/ingestion/loader.py

**What it does:** Full ingestion pipeline orchestrator. Runs all 9 steps sequentially: OE scrape → aftermarket CSV generation → normalization → deduplication → Cohere embedding → Supabase upsert → FTS index rebuild (fetches back from Supabase to get assigned UUIDs) → VIN seed. Prints a final ingestion report. Entry point: `python -m ingestion.loader` from `backend/`.

**External services:** Supabase (upsert + fetch), Cohere (embed), Anthropic (via aftermarket.py), Browserbase/Playwright (via scraper.py), SQLite (FTS index).

**What calls it:** Run directly as a standalone script. Also used as the data-population step before CP-3 verification.

---

## backend/ingestion/eval_runner.py

**What it does:** Runs 5 hardcoded golden queries against the live `/search` SSE endpoint and evaluates results. Checks that non-ambiguous queries return parts and that the Volvo VNL "need brakes" query triggers a `clarify` event. Prints a formatted results table and exits with code 0 (all pass) or 1 (any fail).

**External services:** Live FastAPI `/search` endpoint (requires `uvicorn` running on `localhost:8000`).

**What calls it:** `python -m ingestion.eval_runner` from `backend/` — the CP-5 verification step.

---

## frontend/package.json

**What it does:** Defines the frontend npm project. Dependencies: `react@18`, `react-dom@18`, `react-router-dom@6`. Dev dependencies: TypeScript, Vite, `@vitejs/plugin-react`, Tailwind CSS, PostCSS, autoprefixer, and React type definitions. Scripts: `dev`, `build`, `preview`.

**External services:** None directly — declares packages installed from npm.

**What calls it:** `npm install` (install deps), `npm run dev` (start Vite dev server), Railway Dockerfile build.

---

## frontend/tsconfig.json

**What it does:** TypeScript compiler config for the frontend. Targets ES2020 with `react-jsx` transform, `bundler` module resolution (Vite), strict mode on. `noEmit: true` because Vite handles transpilation; tsc is only used for type-checking.

**External services:** None.

**What calls it:** `npm run build` runs `tsc && vite build`; IDEs use it for type-checking.

---

## frontend/vite.config.ts

**What it does:** Vite bundler config. Registers `@vitejs/plugin-react` (JSX transform + Fast Refresh). No custom aliases or proxy — the API base URL is configured via `VITE_API_BASE_URL` env var read at runtime in `api/client.ts`.

**External services:** None.

**What calls it:** `vite` CLI (dev server and build).

---

## frontend/tailwind.config.ts

**What it does:** Tailwind CSS config. Content paths cover `index.html` and all `src/**/*.{ts,tsx}` files. Extends the theme with a `fade-in` keyframe animation used by `PartCard` to animate streaming part arrivals.

**External services:** None.

**What calls it:** PostCSS processes `src/index.css` through Tailwind at build/dev time.

---

## frontend/postcss.config.js + frontend/src/index.css

**What they do:** `postcss.config.js` chains Tailwind CSS and Autoprefixer PostCSS plugins. `index.css` declares the three Tailwind directives (`@tailwind base/components/utilities`) that PostCSS expands into the full utility stylesheet.

**External services:** None.

**What calls it:** Vite imports `index.css` via `main.tsx`; PostCSS processes it through Tailwind.

---

## frontend/src/types/index.ts

**What it does:** TypeScript type definitions mirroring all backend Pydantic schemas: `Part`, `FitmentResult`, `FitmentConfidence`, `SearchResultPart`, `VINSpec`, `Order`, `OrderCreate`. Single source of truth for all data shapes used across API clients and components.

**External services:** None.

**What calls it:** All `src/api/` modules and all components import types from here.

---

## frontend/src/api/client.ts

**What it does:** Base fetch wrapper. Reads `VITE_API_BASE_URL` from Vite env (defaults to `http://localhost:8000`). Exports `apiGet<T>` and `apiPost<T>` helpers that parse JSON and throw on non-2xx. Also re-exports `API_BASE` for use by `search.ts` which needs direct `fetch` access for SSE streaming.

**External services:** Backend FastAPI server.

**What calls it:** `api/search.ts`, `api/orders.ts`, `api/vin.ts`.

---

## frontend/src/api/search.ts

**What it does:** Implements SSE streaming for the `/search` endpoint. `streamSearch()` opens a `fetch` + `ReadableStream` connection, parses `data:` lines from the stream, and dispatches to typed callbacks: `onPart` (each result card), `onClarify` (ambiguous query question), `onDone`, `onError`. Returns an `AbortController` so callers can cancel on component unmount.

**External services:** Backend `/search` SSE endpoint.

**What calls it:** `SearchPage.tsx` on form submit.

---

## frontend/src/api/orders.ts

**What it does:** Two thin wrappers: `getOrders()` → `GET /orders` → `Order[]`; `createOrder(body)` → `POST /orders` → `Order`.

**External services:** Backend `/orders` endpoints.

**What calls it:** `OrderConfirm.tsx` (create), `OrdersPage.tsx` (list).

---

## frontend/src/api/vin.ts

**What it does:** `decodeVin(vin)` calls `GET /vin/{vin}` and returns a `VINSpec` or `null` on any error. Used on input blur to show vehicle confirmation without blocking the user.

**External services:** Backend `/vin/{vin}` endpoint.

**What calls it:** `SearchBar.tsx` on VIN input blur.

---

## frontend/src/pages/SearchPage.tsx

**What it does:** Top-level state owner for the search flow. Manages part results (appended as SSE events arrive), clarify question, detail panel selection, and order confirm modal. Renders `SearchBar`, streams results via `streamSearch` into `PartCard` list, opens `PartDetail` on card click, opens `OrderConfirm` on "Order" click, and navigates to `/orders` after a confirmed order.

**External services:** Backend `/search` SSE stream (via `streamSearch`), `/orders` POST (via `OrderConfirm`).

**What calls it:** `App.tsx` route `/`.

---

## frontend/src/pages/OrdersPage.tsx

**What it does:** Fetches all orders on mount via `getOrders()` and renders them in `OrderHistory`. Shows loading shimmer while fetching, error message on failure, and the order table on success. Provides a back-to-search link.

**External services:** Backend `GET /orders`.

**What calls it:** `App.tsx` route `/orders`.

---

## frontend/src/App.tsx

**What it does:** Top-level React component. Wraps the app in a `BrowserRouter` and declares two routes: `/` → `SearchPage`, `/orders` → `OrdersPage`.

**External services:** None.

**What calls it:** `main.tsx`.

---

## frontend/src/main.tsx

**What it does:** React entry point. Mounts `<App />` into `#root` wrapped in `StrictMode`, and imports `index.css` (Tailwind directives).

**External services:** None.

**What calls it:** Loaded by `index.html` as the Vite module entry point.

---

## frontend/src/components/FilterPanel.tsx

**What it does:** Renders a filter sidebar with four sections: Source (OEM/Aftermarket checkboxes), Fitment confidence (four confidence levels), Price range (min/max number inputs), and Year range (min/max year inputs, filters by part compatibility range). Exports `FilterState` interface and `DEFAULT_FILTERS` constant used by `ResultsPage`. Stateless — all filter state lives in the parent.

**External services:** None.

**What calls it:** `ResultsPage.tsx` (filter sidebar).

---

## frontend/src/pages/ResultsPage.tsx

**What it does:** Results screen that fires on mount, streams parts via `streamSearch`, and applies `applyFilters` client-side to the received `SearchResultPart[]` array. Manages all result-flow state: `results`, `isStreaming`, `clarifyQuestion`, `searchError`, `selectedResult`, `confirmTarget`, and `filters`. Redirects to `/` if accessed without router state.

**External services:** Backend `/search` SSE stream (via `streamSearch`), `/orders` POST (via `OrderConfirm`).

**What calls it:** `App.tsx` route `/results`.

---

## UI Design System (dark theme, 2026-04-26)

**Applied across:** All component and page files.

Color tokens used: `zinc-950` (page bg), `zinc-900` (cards/panels), `zinc-800` (inputs/elevated), `zinc-700` (borders/toggles), `orange-500` (primary CTA), `orange-400` (hover/accent text), `white`/`zinc-400`/`zinc-500` (text hierarchy).

Branding: "HeaviAI Procurement CoPilot" with "Procurement" in orange on the landing page.

---
