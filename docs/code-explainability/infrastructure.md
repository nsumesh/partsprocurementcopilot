# Infrastructure

## migrations/001_initial.sql

**What it does:** Defines the Supabase Postgres schema. Creates three tables — `parts` (canonical OE + aftermarket catalog with pgvector embedding column), `orders` (intent records with no payment logic), and `vin_cache` (decoded VIN records). Also creates the `match_parts` SQL function used by the API for vector similarity search, an IVFFlat index on the embedding column, and permissive RLS policies for the single-user tool.

**External services:** Applied manually via Supabase SQL editor.

**What calls it:** Run once at project setup. The `ingestion/loader.py` pipeline writes to these tables. The FastAPI app reads from them at query time.

---

## migrations/002_vendor_outreach.sql

**What it does:** Reconstructed v2.0 vendor-outreach schema so the repo is reproducible from source — written idempotently (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, drop-and-recreate policies) so it is safe on a fresh project and on the live DB where these tables were originally created out-of-band via the SQL editor. Creates `vendors`, `vendor_parts`, `procurement_jobs` (including `attempt_count` and the 11-state status CHECK with terminal `failed`), and the append-only `procurement_events` log. Adds indexes for the worker's 30-second poll predicates and the board queries, enables RLS with SELECT-only policies for the anon role (the browser holds the anon key for Realtime; all writes go through the service-role backend, so the state machine can't be bypassed client-side), and adds `procurement_jobs` to the `supabase_realtime` publication for the job board's WebSocket subscription.

**External services:** Applied manually via Supabase SQL editor.

**What calls it:** Run once after `001_initial.sql`. `ingestion/vendor_seeder.py` populates `vendors`/`vendor_parts`; the API and worker read/write `procurement_jobs`/`procurement_events`.

---

## migrations/003_retrieval_fixes.sql

**What it does:** Replaces the pgvector index from 001. That migration created an IVFFlat index with `lists = 100` on a ~170-row table (guidance is lists ≈ rows/1000) and created it before any data existed, so the centroids were never trained and queries scanned ~1–2 near-random vectors. Drops it and creates an HNSW index (`vector_cosine_ops`), which needs no training step, works on empty tables, and is the better choice at this corpus size.

**External services:** Applied manually via Supabase SQL editor.

**What calls it:** Run once after `002_vendor_outreach.sql`. The `match_parts` RPC uses the index at query time.

---

## .env.example

**What it does:** Documents every environment variable the system requires. Covers Supabase credentials, Anthropic and Cohere API keys, Browserbase credentials for the ingestion scraper, and three frontend Vite env vars: `VITE_API_BASE_URL` (backend URL), `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` (needed by `ProcurementBoard` for Supabase Realtime WebSocket). Developers copy this to `.env` and fill in real values; `.env` is gitignored.

**External services:** None — this is documentation, not executable.

**What calls it:** Referenced by `backend/app/config.py` (pydantic-settings reads `.env`), and by the frontend Vite build (`VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`).

---

## backend/Dockerfile

**What it does:** Builds the FastAPI backend into a `python:3.12-slim` image. Installs `uv`, syncs dependencies from `uv.lock` with `--frozen --no-dev`, copies `app/` and `ingestion/` into the image. Uses shell-form CMD so `${PORT:-8000}` is expanded at runtime — Railway injects `$PORT` dynamically; the `:-8000` fallback keeps local runs working without setting the variable.

**External services:** None at build time. Connects to Supabase, Anthropic, and Cohere at runtime via environment variables.

**What calls it:** Railway build system (GitHub-connected deploy from `backend/` root directory).

---

## backend/railway.toml

**What it does:** Per-service Railway config-as-code for the backend. Declares `builder = "DOCKERFILE"`, `dockerfilePath = "Dockerfile"`, healthcheck path, and restart policy. Scoped to the `backend/` root directory — Railway reads it when the service's Root Directory is set to `backend/`.

**External services:** Railway build and deploy infrastructure.

**What calls it:** Railway on every GitHub push to `main`.

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

## frontend/railway.toml

**What it does:** Per-service Railway config-as-code for the frontend. Declares `builder = "DOCKERFILE"`, `dockerfilePath = "Dockerfile"`, healthcheck path, and restart policy. Scoped to the `frontend/` root directory.

**External services:** Railway build and deploy infrastructure.

**What calls it:** Railway on every GitHub push to `main`.
