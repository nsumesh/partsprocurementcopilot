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

**What it does:** Documents every environment variable the system requires. Covers Supabase credentials, Anthropic and Cohere API keys, Browserbase credentials for the ingestion scraper, and three frontend Vite env vars: `VITE_API_BASE_URL` (backend URL), `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` (needed by `ProcurementBoard` for Supabase Realtime WebSocket). Developers copy this to `.env` and fill in real values; `.env` is gitignored.

**External services:** None — this is documentation, not executable.

**What calls it:** Referenced by `backend/app/config.py` (pydantic-settings reads `.env`), and by the frontend Vite build (`VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`).

---

## backend/app/config.py

**What it does:** Defines the `Settings` class using `pydantic-settings`, reading all environment variables from `.env`. Exposes a `get_settings()` singleton via `@lru_cache` used as a FastAPI dependency throughout the app.

**External services:** None — reads local `.env` file.

**What calls it:** `app/main.py` (lifespan), `app/api/*.py` routes (via `Depends(get_settings)`), `app/vin/decoder.py`, ingestion scripts.

---

## backend/app/main.py

**What it does:** Creates the FastAPI application with CORS middleware and registers five API routers (`/vin`, `/search`, `/orders`, `/vendors`, `/procurement`). On startup, initialises the Supabase client, rebuilds the SQLite FTS index if missing or empty, and starts `job_processor_loop` as an `asyncio.create_task`. The task handle is cancelled cleanly on shutdown.

**External services:** Supabase (via `db/supabase.py`), SQLite FTS (via `db/sqlite_fts.py`). Worker task connects to Supabase and Anthropic internally.

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

## frontend/src/pages/ProcurementBoard.tsx

**What it does:** Full-page job tracking board at `/procurement`. On mount, fetches all procurement jobs via `getProcurementJobs()` and opens a Supabase Realtime channel (`procurement_jobs_realtime`) subscribed to `postgres_changes` on the `procurement_jobs` table. Incoming change events upsert into the local `jobs` state and also patch `selected` if the updated job is currently open. Renders jobs as a table of `ProcurementJobRow` rows; clicking a row opens `VendorOutreachPanel` as a slide-in panel. `handleJobUpdate` propagates panel-driven mutations (send follow-up, accept, reject) back into both `jobs` and `selected`. Shows loading, error, and empty-state slots.

**External services:** Backend `GET /procurement/jobs` (initial load), Supabase Realtime WebSocket (`VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` env vars).

**What calls it:** `App.tsx` route `/procurement`. Navigation link present in `ResultsPage` header and within the board's own header.

---

## frontend/src/App.tsx

**What it does:** Top-level React component. Wraps the app in a `BrowserRouter` and declares four routes: `/` → `SearchPage`, `/results` → `ResultsPage`, `/orders` → `OrdersPage`, `/procurement` → `ProcurementBoard`.

**External services:** None.

**What calls it:** `main.tsx`.

---

## frontend/src/main.tsx

**What it does:** React entry point. Mounts `<App />` into `#root` wrapped in `StrictMode`, and imports `index.css` (Tailwind directives).

**External services:** None.

**What calls it:** Loaded by `index.html` as the Vite module entry point.

---

## frontend/src/components/SearchBar.tsx

**What it does:** Controlled form with three inputs — VIN (text, 17-char max), query (textarea), and urgency toggle (Standard / Urgent button group). On VIN input blur, calls `decodeVin` and shows the vehicle confirmation ("2014 Kenworth T680 — Paccar MX-13") in orange, or an error in red if the VIN is unrecognized. Submit button is disabled until VIN is exactly 17 characters and query is non-empty.

**External services:** Backend `GET /vin/{vin}` (via `decodeVin`).

**What calls it:** `SearchPage.tsx`.

---

## frontend/src/components/PartCard.tsx

**What it does:** Renders a single search result as a dark card with fade-in animation on mount (triggered as cards stream in). Displays part name, part number (monospace), category chip, source chip (OEM=blue / Aftermarket=purple), fitment confidence badge (color-coded), and price. The full card is clickable to open the detail panel.

**External services:** None.

**What calls it:** `ResultsPage.tsx` — one card per item in the filtered results array.

---

## frontend/src/components/PartDetail.tsx

**What it does:** Slide-in right panel showing full part detail. Sections: fitment confidence badge + reasoning paragraph, brand + unit price, description, specifications key/value table (from `part.attributes`), vendor sources list (vendor name, link). Two footer buttons: "Order This Part" (`onOrder`) for a simple intent order and "Procure →" (`onProcure`) which kicks off the vendor outreach flow. Rendered on top of a blurred dark backdrop; clicking outside or the X button closes it.

**External services:** None.

**What calls it:** `ResultsPage.tsx` — rendered when `selectedResult` is set.

---

## frontend/src/components/OrderConfirm.tsx

**What it does:** Modal overlay for confirming an order. Shows part name and number, a quantity number input (min 1, default 1), and a live-calculated total (`price × qty`). On confirm, calls `createOrder` to POST to the backend then calls `onConfirm` to navigate to orders. Animated with `fade-up` on mount.

**External services:** Backend `POST /orders` (via `createOrder`).

**What calls it:** `ResultsPage.tsx` — rendered when `confirmTarget` is set.

---

## frontend/src/components/OrderHistory.tsx

**What it does:** Renders all past orders as a dark-themed table. Columns: Part Name, Part Number, Qty, VIN, Urgency (urgent gets an orange badge), Date. Shows an empty-state message when no orders exist. Stateless — receives the `orders` array as a prop.

**External services:** None.

**What calls it:** `OrdersPage.tsx`.

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

## backend/Dockerfile

**What it does:** Builds the FastAPI backend into a `python:3.12-slim` image. Installs `uv`, syncs dependencies from `uv.lock` with `--frozen --no-dev`, copies `app/` and `ingestion/` into the image. Uses shell-form CMD so `${PORT:-8000}` is expanded at runtime — Railway injects `$PORT` dynamically; the `:-8000` fallback keeps local runs working without setting the variable.

**External services:** None at build time. Connects to Supabase, Anthropic, and Cohere at runtime via environment variables.

**What calls it:** Railway build system (GitHub-connected deploy from `backend/` root directory).

---

## frontend/Dockerfile

**What it does:** Two-stage build. Stage 1: `node:20-alpine` installs dependencies and runs `npm run build` with `VITE_API_BASE_URL` baked in as a build arg. Stage 2: `nginx:alpine` serves the built `dist/` directory. At startup, runs `envsubst '${PORT}'` to substitute Railway's dynamic port into the nginx config template before nginx reads it.

**External services:** None at runtime. The built JS bundle calls the backend API directly from the user's browser.

**What calls it:** Railway build system (GitHub-connected deploy from `frontend/` root directory).

---

## frontend/nginx.conf

**What it does:** nginx server block template for the React SPA. Listens on `${PORT}` (substituted at startup by `envsubst`). Enables gzip, serves static assets with 1-year immutable cache headers, and falls back all unmatched routes to `index.html` so React Router handles client-side navigation.

**External services:** None.

**What calls it:** `frontend/Dockerfile` CMD — `envsubst` writes the resolved config to `default.conf` before nginx starts.

---

## backend/railway.toml / frontend/railway.toml

**What it does:** Per-service Railway config-as-code. Declares `builder = "DOCKERFILE"`, `dockerfilePath = "Dockerfile"`, healthcheck path, and restart policy. Each file is scoped to its own service directory — Railway reads it when the service's Root Directory is set to `backend/` or `frontend/` respectively.

**External services:** Railway build and deploy infrastructure.

**What calls it:** Railway on every GitHub push to `main`.

---

## backend/app/schemas/procurement.py

**What it does:** Pydantic models for the vendor outreach feature. Defines `JobStatus` as a Literal union of all 10 state machine states. `Vendor` models the 10 vendor records (name, email, region, type, brands, response_rate). `VendorPart` models the explicit vendor×part mapping (pricing, delivery_estimate string, delivery_hours int, in_stock). `ProcurementJobCreate` is the POST body for creating a job. `ProcurementJob` is the full snapshot model including all generated/received email text, parsed fields from the vendor response, ranking_score, and respond_at timestamp. `ProcurementEvent` models one immutable event log row (from/to status, actor, metadata).

**External services:** None.

**What calls it:** `api/vendors.py`, `api/procurement.py` (request/response types). `workers/job_processor.py` uses `JobStatus` states for transition logic.

---

## backend/ingestion/vendor_seeder.py

**What it does:** Seeds the `vendors` and `vendor_parts` tables. `seed_vendors` upserts 10 hardcoded vendors from `vendors.md` (on_conflict="name"). `seed_vendor_parts` fetches all parts and all vendors, splits vendors into OE pool and Aftermarket pool by vendor type, then for each part uses `re.search` (case-insensitive) on `part.source` to pick the matching pool and randomly samples 2–5 vendors from it. Each mapping row gets a random `delivery_estimate` string from a fixed pool, its corresponding `delivery_hours` integer, a `list_price` with ±25% variation from the part's catalog price, and an 80% probability of `in_stock=True`. Can be run standalone via `python -m ingestion.vendor_seeder` or called from `loader.py`.

**External services:** Supabase (`vendors`, `vendor_parts`, `parts` tables).

**What calls it:** `ingestion/loader.py` (after VIN seed step). Also runnable directly for re-seeding vendors without a full ingestion run.

---

## backend/ingestion/loader.py (vendor seeder extension)

**What it does:** Extended with two calls after the existing 9-step pipeline — `seed_vendors(supabase)` and `seed_vendor_parts(supabase)` — appended as separate logic without renumbering the original steps. The vendor seeding runs after parts are already in Supabase so `seed_vendor_parts` can fetch assigned UUIDs.

**External services:** Same as before — Supabase, Cohere, Anthropic, Browserbase/Playwright, SQLite.

**What calls it:** `python -m ingestion.loader` from `backend/`.

---


## frontend/src/components/VendorSelector.tsx

**What it does:** Modal for selecting a vendor before creating a procurement job. Fetches `VendorPart[]` from `getVendorsForPart` on mount and renders each as a clickable card showing vendor name, type badge, response rate badge (green/yellow/red), ETA, and price. When urgency is `urgent`, renders a datetime-local input pre-filled with `urgencyDeadline` (min = now+2h) and dims vendors whose `delivery_hours` would exceed the deadline with an amber warning. Clicking a card calls `onSelect(vendorPart, deadline)`.

**External services:** Backend `/vendors/part/{part_id}` (via `getVendorsForPart`).

**What calls it:** `ResultsPage` — opened when user clicks "Create Procurement Request" in `PartDetail`.

---

## frontend/src/components/OutreachConfirm.tsx

**What it does:** Modal showing the Haiku-generated outreach email in an editable `textarea`. User can edit before sending. "Send Outreach" calls `sendOutreach(job.id)`, which transitions the job to `outreach_sent`. Calls `onConfirm(updatedJob)` on success.

**External services:** Backend `POST /procurement/jobs/{id}/send` (via `sendOutreach`).

**What calls it:** `ResultsPage` — shown after job is created and vendor is selected.

---

## frontend/src/components/VendorOutreachPanel.tsx

**What it does:** Right-side slide-in panel (same pattern as `PartDetail`) showing the full lifecycle of a procurement job. Sections: vendor info card, collapsible outreach email, vendor response email, parsed fields table (missing values shown in amber), follow-up textarea editor when status is `follow_up_required`, ranking score breakdown with three `ScoreBar` sub-components when ranked, Accept/Reject sticky footer when ranked. All actions (send follow-up, accept, reject) call the relevant API function via the shared `act()` helper and propagate the updated job to the parent via `onJobUpdate`.

**External services:** Backend procurement endpoints (via `sendFollowup`, `acceptJob`, `rejectJob`).

**What calls it:** `ProcurementBoard` — opened when a job row is clicked.

---

## frontend/src/components/ProcurementJobRow.tsx

**What it does:** Single table row for the procurement job board. Displays part name + part number, vendor name + type, status badge (color-coded with pulse animation for awaiting states), time elapsed since last event, and a "last action" string derived from the final event in `job.events`. Clicking the row calls `onClick`.

**External services:** None.

**What calls it:** `ProcurementBoard` — one row per job in the jobs table.

---

## frontend/src/types/index.ts (vendor outreach extensions)

**What it does:** Extended with six new types for the vendor outreach feature: `Vendor`, `VendorPart`, `JobStatus` union, `ProcurementEvent`, `ProcurementJob` (full job snapshot including all email fields, parsed fields, ranking score, and nested vendor + events), `ProcurementJobCreate` (POST body). Mirrors the backend Pydantic schemas exactly.

**External services:** None.

**What calls it:** `api/vendors.ts`, `api/procurement.ts`, all new components (VendorSelector, OutreachConfirm, VendorOutreachPanel, ProcurementJobRow, ProcurementBoard).

---

## frontend/src/api/vendors.ts

**What it does:** Single function `getVendorsForPart(part_id)` — calls `GET /vendors/part/{part_id}` and returns `VendorPart[]`.

**External services:** Backend `/vendors/part/{part_id}` endpoint.

**What calls it:** `VendorSelector` component on mount.

---

## frontend/src/api/procurement.ts

**What it does:** Seven typed wrappers covering the full job lifecycle: `createProcurementJob`, `getProcurementJobs`, `getProcurementJob`, `sendOutreach`, `sendFollowup` (accepts optional edited email body), `acceptJob`, `rejectJob`. All use `apiGet`/`apiPost` from `client.ts`.

**External services:** Backend `/procurement/*` endpoints.

**What calls it:** `ResultsPage` (create + send), `VendorOutreachPanel` (followup, accept, reject), `ProcurementBoard` (list).

---

## frontend/package.json (vendor outreach extension)

**What it does:** Added `@supabase/supabase-js: ^2.0.0` to dependencies for Supabase Realtime subscription on the job board.

**External services:** npm registry at install time; Supabase WebSocket at runtime.

**What calls it:** `ProcurementBoard` page imports `createClient` from `@supabase/supabase-js`.

---

## backend/app/api/vendors.py

**What it does:** Exposes `GET /vendors/part/{part_id}` — returns all in-stock vendor-part mappings for a given part, with the related vendor record embedded. Returns 404 if no vendors are found.

**External services:** Supabase (`vendor_parts` + `vendors` JOIN via `fetch_vendors_for_part`).

**What calls it:** Frontend `api/vendors.ts` — called when VendorSelector modal opens to populate the vendor list.

---

## backend/app/api/procurement.py

**What it does:** Seven endpoints covering the full procurement job lifecycle. `POST /jobs` fetches the part, vendor, and decoded VIN spec, generates the outreach email via `email_generator`, inserts the job at `created` status, and writes the first event row. `POST /jobs/{id}/send` and `/followup` transition status and compute `respond_at` using `_respond_at()` — a helper that maps vendor `response_rate` to 3 / 10–15 / 20 minute delays. `/followup` accepts an optional edited `follow_up_email` body. `/accept` and `/reject` guard that the job is in `ranked` status before transitioning. All actions write a `procurement_events` row. `FollowUpBody` is a local Pydantic model for the optional follow-up body.

**External services:** Supabase (jobs, events, vendors, parts tables), Anthropic API (via `email_generator` on job creation), NHTSA/VIN cache (via `decode_vin`).

**What calls it:** Frontend `api/procurement.ts` — all job lifecycle actions.

---

## backend/app/workers/job_processor.py

**What it does:** Background async coroutine started at FastAPI lifespan. Polls every 30 seconds. In each cycle: (1) fetches jobs in `outreach_sent` or `follow_up_sent` whose `respond_at <= now()`, simulates the vendor response via `response_simulator`, parses it via `email_parser`, generates a follow-up email if fields are missing (→ `follow_up_required`) or marks the job `confirmed` if all fields present, writes a `procurement_events` row for each transition. (2) Fetches `confirmed` jobs with null `ranking_score`, computes the composite score via `ranker`, transitions to `ranked`. Creates its own `AsyncAnthropic` client from settings — does not depend on `app.state.anthropic`. Per-job `try/except` keeps one failed job from blocking the rest; errors are logged and written to `procurement_events` metadata.

**External services:** Supabase (`procurement_jobs`, `procurement_events`), Anthropic API (via agent modules).

**What calls it:** `app/main.py` lifespan — started as `asyncio.create_task(job_processor_loop(app.state))` and cancelled on shutdown (Batch 8).

---

## backend/app/agents/email_generator.py

**What it does:** Generates a professional parts outreach email using Claude Haiku. Accepts the part dict, vendor dict, decoded VIN spec dict, urgency, and optional deadline. Appends an urgency line when the request is urgent and a deadline is set. Returns plain email body text — no JSON, no markdown fences expected.

**External services:** Anthropic API (`claude-haiku-4-5-20251001`, temperature=0).

**What calls it:** `api/procurement.py` (POST /procurement/jobs — generates outreach email on job creation).

---

## backend/app/agents/response_simulator.py

**What it does:** Simulates a vendor's email reply using Claude Haiku. Derives the vendor's communication tone from their `type` field (formal for OE Manufacturers, terse for OE truck-stop vendors, casual for Aftermarket). Calculates `P(field_missing) = (1 - response_rate) × 0.6` per field and randomly omits fields to exercise the follow-up path. Passes field values and omission list to Haiku so the reply is realistic but intentionally incomplete for lower-rated vendors.

**External services:** Anthropic API (`claude-haiku-4-5-20251001`, temperature=0).

**What calls it:** `workers/job_processor.py` when a job's `respond_at` passes.

---

## backend/app/agents/email_parser.py

**What it does:** Extracts four structured fields from a vendor email using Claude Haiku: `availability_status`, `unit_price` (float), `quantity_available` (int), `estimated_delivery_date` (string). Returns a dict with a `missing_fields` list for any fields that were null. Uses the same markdown-fence-strip + `json.loads` pattern as `pipeline/intent.py`.

**External services:** Anthropic API (`claude-haiku-4-5-20251001`, temperature=0).

**What calls it:** `workers/job_processor.py` after `simulate_vendor_response` or a real follow-up response is received.

---

## backend/app/agents/followup_generator.py

**What it does:** Generates a follow-up email when the parsed vendor response is missing required fields. Passes the original outreach, the vendor's reply, and human-readable labels for each missing field to Claude Haiku. Returns plain email body text for the operator to review and edit before sending.

**External services:** Anthropic API (`claude-haiku-4-5-20251001`, temperature=0).

**What calls it:** `workers/job_processor.py` when `parse_vendor_response` returns non-empty `missing_fields`.

---

## backend/app/agents/ranker.py

**What it does:** Pure Python. Computes a composite ranking score from three inputs: `price_score = 1 - (unit_price / max_catalog_price)`, `delivery_score = 1 - (delivery_hours / 480)` (480h = 20-day ceiling), weighted `0.4 / 0.4 / 0.2` with `response_rate`. Output is clamped to [0, 1].

**External services:** None.

**What calls it:** `workers/job_processor.py` when a job transitions to `confirmed` and `ranking_score` is null.

---

## backend/app/db/supabase.py (vendor outreach extensions)

**What it does:** Nine new async functions added after the existing parts/orders/vin helpers. `fetch_vendors_for_part` joins `vendor_parts` + `vendors` inline via PostgREST foreign key syntax and filters to in-stock rows only. `insert_procurement_job` and `update_procurement_job` handle job creation and partial field updates. `fetch_procurement_jobs` and `fetch_procurement_job` embed the related vendor record for job board display. `fetch_pending_simulations` pulls jobs in `outreach_sent` or `follow_up_sent` whose `respond_at <= now()` and also joins `vendor_parts` so the worker has pricing and delivery data. `fetch_confirmed_unranked` uses `.is_("ranking_score", "null")` for the Postgres IS NULL check. `insert_procurement_event` and `fetch_job_events` manage the immutable transition log.

**External services:** Supabase Postgres (`vendor_parts`, `vendors`, `procurement_jobs`, `procurement_events` tables).

**What calls it:** `api/vendors.py`, `api/procurement.py`, `workers/job_processor.py`.

---

## Batch 11 — Frontend Integration

### frontend/src/components/SearchBar.tsx (edited)

**What changed:** Added `urgency_deadline: string | null` as fourth param to the `onSearch` prop. Added `urgencyDeadline` state (empty string default). Clicking "Urgent" now calls `handleSetUrgent()` which pre-fills the deadline to now+2h if not already set. A `datetime-local` input with an orange border appears below the urgency toggle when urgent is active; the `min` attribute is recomputed from `minDeadline()` on every render to prevent past dates. On submit, passes the deadline as the fourth arg (null when standard).

**External services:** None.

**What calls it:** `SearchPage.tsx`.

---

### frontend/src/pages/SearchPage.tsx (edited)

**What changed:** `onSearch` callback now accepts the fourth `urgency_deadline` parameter and includes it in the navigate state: `{ vin, query, urgency, urgency_deadline }`.

**External services:** None.

**What calls it:** `SearchBar.tsx` via `onSearch` prop.

---

### frontend/src/pages/ResultsPage.tsx (edited)

**What changed:**
- `LocationState` extended with `urgency_deadline: string | null`
- Imports added: `createProcurementJob` from `api/procurement`, `VendorSelector`, `OutreachConfirm` components, `VendorPart`/`ProcurementJob` types
- Three new state vars: `procureTarget` (the part being procured), `selectedVendorPart` (vendor chosen in selector), `procurementJob` (job created via API), `procureDeadline`
- "Procurement" nav link added to header alongside "Orders"
- `PartDetail` now receives `onProcure` which sets `procureTarget`, `procureDeadline`, closes the detail panel
- `VendorSelector` modal mounts when `procureTarget` is set and no vendor chosen yet; on select, calls `createProcurementJob` to create the job and transitions to `OutreachConfirm`
- `OutreachConfirm` modal mounts when `procurementJob` and `selectedVendorPart` are both set; on confirm (after `sendOutreach` inside the component), navigates to `/procurement` and clears all procure state

**Flow:** PartDetail "Procure →" → VendorSelector → `createProcurementJob` → OutreachConfirm → `sendOutreach` (inside OutreachConfirm) → navigate("/procurement")

**External services:** Supabase via API (`POST /procurement/jobs`, `POST /procurement/jobs/{id}/send`).

**What calls it:** User click from `PartDetail` footer.

---
