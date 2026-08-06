# Backend — Database

## backend/app/db/supabase.py

**What it does:** Wraps the `supabase-py` async client with typed helper functions for every DB operation the app needs. Core helpers: fetching and upserting parts, inserting and listing orders, reading/writing the VIN cache, and calling the `match_parts` RPC for vector similarity search. Vendor outreach helpers (ten additional async functions): `fetch_vendors_for_part` (joins `vendor_parts` + `vendors` inline via PostgREST foreign key syntax, filters to in-stock rows); `insert_procurement_job` and `update_procurement_job` (job creation and partial field updates — these and `insert_procurement_event` now raise `RuntimeError` with a descriptive message instead of an opaque `IndexError` when the operation matches zero rows); `update_job_if_status` (compare-and-set: the expected-status predicate rides on the UPDATE itself and returns `None` if another actor transitioned the job first — the primitive behind all API and worker CAS transitions); `fetch_procurement_jobs` and `fetch_procurement_job` (embed the related vendor record for job board display; the list variant also embeds `events:procurement_events(*)` sorted oldest-first); `fetch_pending_simulations` (jobs in `outreach_sent` or `follow_up_sent` whose `respond_at <= now()`, joins `vendor_parts` for pricing and delivery data); `fetch_confirmed_unranked` (uses `.is_("ranking_score", "null")` for the Postgres IS NULL check); `insert_procurement_event` and `fetch_job_events` (immutable transition log).

**External services:** Supabase Postgres — all tables: `parts`, `orders`, `vin_cache`, `vendor_parts`, `vendors`, `procurement_jobs`, `procurement_events`, plus the `match_parts` pgvector RPC.

**What calls it:** `app/main.py` (initialises the client), `pipeline/retrieve.py` (vector search), `pipeline/fitment.py` (part number validation), `api/orders.py`, `api/vin.py`, `api/vendors.py`, `api/procurement.py`, `workers/job_processor.py`, `db/sqlite_fts.py` (FTS rebuild), ingestion scripts.

---

## backend/app/db/sqlite_fts.py

**What it does:** Manages a local SQLite FTS5 index over the parts catalog. `build()` creates the virtual table with a porter tokeniser and a `parts_lookup` rowid→part_id mapping, running as a single transaction under a `threading.Lock` with rollback on failure. `query()` tokenises the input and ORs the individually-quoted tokens into a bag-of-words BM25 match — a single quoted string would be an exact-phrase match returning zero rows for any natural-language query — and returns `(part_id, score)` pairs. Every operation opens its own short-lived sqlite3 connection; the previous shared `check_same_thread=False` connection was unsafe across the event loop and executor threads. `rebuild_if_missing()` is called on startup — if the file is absent or empty it fetches all parts from Supabase and rebuilds in a thread executor obtained via `asyncio.get_running_loop()`.

**External services:** SQLite (local file), Supabase (via `fetch_all_parts` for rebuild).

**What calls it:** `app/main.py` (startup rebuild), `pipeline/retrieve.py` (BM25 query leg), `ingestion/loader.py` (full rebuild after ingestion).
