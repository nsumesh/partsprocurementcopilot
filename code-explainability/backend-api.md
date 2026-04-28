# Backend — API

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

## backend/app/api/vendors.py

**What it does:** Exposes `GET /vendors/part/{part_id}` — returns all in-stock vendor-part mappings for a given part, with the related vendor record embedded. Returns 404 if no vendors are found.

**External services:** Supabase (`vendor_parts` + `vendors` JOIN via `fetch_vendors_for_part`).

**What calls it:** Frontend `api/vendors.ts` — called when VendorSelector modal opens to populate the vendor list.

---

## backend/app/api/procurement.py

**What it does:** Seven endpoints covering the full procurement job lifecycle. `POST /jobs` fetches the part, vendor, and decoded VIN spec, generates the outreach email via `email_generator`, inserts the job at `created` status, and writes the first event row. `POST /jobs/{id}/send` and `/followup` transition status and compute `respond_at` using `_respond_at()` — a helper that maps vendor `response_rate` to 3 / 10–15 / 20 minute delays. `/followup` accepts an optional edited `follow_up_email` body. `/accept` and `/reject` guard that the job is in `ranked` status before transitioning. All actions write a `procurement_events` row. `FollowUpBody` is a local Pydantic model for the optional follow-up body.

**External services:** Supabase (jobs, events, vendors, parts tables), Anthropic API (via `email_generator` on job creation), NHTSA/VIN cache (via `decode_vin`).

**What calls it:** Frontend `api/procurement.ts` — all job lifecycle actions.
