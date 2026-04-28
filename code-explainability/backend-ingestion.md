# Backend — Ingestion

## backend/ingestion/scraper.py

**What it does:** Scrapes OE parts from finditparts.com across 10 commercial truck part categories using Browserbase (remote Chrome) + Playwright. Loads the homepage once, then for each category fills `#searcher_s` and calls `form.requestSubmit()` via `page.evaluate()` (immune to modal overlay blocking). Two grids co-exist in the DOM: `.product_results_grid.loading` (skeleton, always present) and `.product_results_grid.loaded` (injected by AJAX when results arrive). Waits specifically for `.product_results_grid.loaded`, then selects `.product_results_grid.loaded .product_search_result` cards (scoped to avoid skeleton). Extracts all data in one `card.evaluate()` JS round-trip: `data-name`, `data-price`, `data-brand`, `data-category`, `data-category2`, description from `[itemprop="description"]`. Manufacturer part number is extracted by stripping the brand prefix from `data-name` (format: `"{BRAND} {PART_NUMBER}"`). Returns a list of raw dicts ready for `normalize_oe()`.

**External services:** Browserbase (remote browser sessions), finditparts.com (scraped), Playwright (browser automation).

**What calls it:** `ingestion/loader.py` (step 1/9).

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

## backend/ingestion/aftermarket.py

**What it does:** Takes the scraped OE parts, extracts unique categories, and calls `claude-sonnet-4-6` to generate 4 realistic aftermarket alternative SKUs per category (brand, price, fit_notes, attributes). Writes the results to a CSV file at `data/aftermarket.csv`. The generated data gives the retrieval pipeline aftermarket alternatives to surface alongside OE parts.

**External services:** Anthropic API (`claude-sonnet-4-6`).

**What calls it:** `ingestion/loader.py` (step 2/9, after OE scrape).

---

## backend/ingestion/loader.py

**What it does:** Full ingestion pipeline orchestrator. Runs 9 steps sequentially: OE scrape → aftermarket CSV generation → normalization → deduplication → Cohere embedding → Supabase upsert → FTS index rebuild (fetches back from Supabase to get assigned UUIDs) → VIN seed. After the 9-step pipeline, additionally calls `seed_vendors(supabase)` and `seed_vendor_parts(supabase)` — these run after parts are in Supabase so `seed_vendor_parts` can fetch assigned UUIDs. Prints a final ingestion report. Entry point: `python -m ingestion.loader` from `backend/`.

**External services:** Supabase (upsert + fetch), Cohere (embed), Anthropic (via aftermarket.py), Browserbase/Playwright (via scraper.py), SQLite (FTS index).

**What calls it:** Run directly as a standalone script. Also used as the data-population step before CP-3 verification.

---

## backend/ingestion/eval_runner.py

**What it does:** Runs 5 hardcoded golden queries against the live `/search` SSE endpoint and evaluates results. Checks that non-ambiguous queries return parts and that the Volvo VNL "need brakes" query triggers a `clarify` event. Prints a formatted results table and exits with code 0 (all pass) or 1 (any fail).

**External services:** Live FastAPI `/search` endpoint (requires `uvicorn` running on `localhost:8000`).

**What calls it:** `python -m ingestion.eval_runner` from `backend/` — the CP-5 verification step.

---

## backend/ingestion/vin_seeds.py

**What it does:** Hardcodes decoded VIN records for the 5 eval vehicles (Kenworth T680, Freightliner Cascadia, Volvo VNL, Peterbilt 386, Mack Pinnacle). `seed_vins()` upserts all 5 records to the `vin_cache` Supabase table so the eval queries never depend on a live NHTSA API call.

**External services:** Supabase (`vin_cache` table).

**What calls it:** `ingestion/loader.py` at the end of the ingestion pipeline (step 9/9).

---

## backend/ingestion/vendor_seeder.py

**What it does:** Seeds the `vendors` and `vendor_parts` tables. `seed_vendors` upserts 10 hardcoded vendors from `vendors.md` (on_conflict="name"). `seed_vendor_parts` fetches all parts and all vendors, splits vendors into OE pool and Aftermarket pool by vendor type, then for each part uses `re.search` (case-insensitive) on `part.source` to pick the matching pool and randomly samples 2–5 vendors from it. Each mapping row gets a random `delivery_estimate` string from a fixed pool, its corresponding `delivery_hours` integer, a `list_price` with ±25% variation from the part's catalog price, and an 80% probability of `in_stock=True`. Can be run standalone via `python -m ingestion.vendor_seeder` or called from `loader.py`.

**External services:** Supabase (`vendors`, `vendor_parts`, `parts` tables).

**What calls it:** `ingestion/loader.py` (after VIN seed step). Also runnable directly for re-seeding vendors without a full ingestion run.
