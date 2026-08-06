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

**What it does:** Exposes `POST /search` as a Server-Sent Events stream. Orchestrates the full pipeline — VIN decode → intent parse → embed → retrieve 50 candidates (`_CANDIDATE_K`, pgvector + BM25 + RRF) → restore RRF order (`fetch_parts_by_ids` returns arbitrary DB order) → rerank down to 10 (`_TOP_K`) → per-part fitment — yielding one SSE `part` event per result as it resolves. A failed fitment call for a single part yields a LOW-confidence fallback result instead of killing the stream, and a `finally` block cancels in-flight fitment tasks on error or client disconnect so orphaned LLM calls don't keep running. Pipeline exceptions are logged with the raw traceback while the client sees only a generic error message. Short-circuits with a `clarify` event if the intent is ambiguous. Model selection (Sonnet vs Haiku) is driven by the `urgency` field on the request; `SearchRequest` also carries an optional `urgency_deadline` that flows into procurement job creation.

**External services:** Anthropic API (intent + fitment), Cohere (embed + rerank), Supabase pgvector, SQLite FTS — all via pipeline modules.

**What calls it:** Frontend `api/search.ts` via `fetch` + `ReadableStream`.

---

## backend/app/api/vendors.py

**What it does:** Exposes `GET /vendors/part/{part_id}` — returns all in-stock vendor-part mappings for a given part, with the related vendor record embedded. Returns 404 if no vendors are found.

**External services:** Supabase (`vendor_parts` + `vendors` JOIN via `fetch_vendors_for_part`).

**What calls it:** Frontend `api/vendors.ts` — called when VendorSelector modal opens to populate the vendor list.

---

## backend/app/api/procurement.py

**What it does:** Eight endpoints covering the full procurement job lifecycle. `POST /jobs` fetches the part, vendor, and decoded VIN spec, generates the outreach email via `email_generator`, inserts the job at `created` status, and writes the first event row. All five action endpoints — `/send`, `/followup`, `/confirm`, `/accept`, `/reject` — transition through a shared `_cas_transition()` helper: the expected-status predicate rides on the UPDATE itself (via `update_job_if_status`), so two racing requests can't both pass a read-then-check guard — the loser gets a 409 carrying the job's actual status, and the winner writes the `procurement_events` row. `/send` and `/followup` compute `respond_at` using `_respond_at()` — a helper that maps vendor `response_rate` to a 20 / 30 / 60 second simulated reply delay. `/send` accepts an optional `{outreach_email}` body (`SendBody`) so operator edits from the confirm modal are persisted before sending; `/followup` accepts an optional edited `follow_up_email` body (`FollowUpBody`).

**External services:** Supabase (jobs, events, vendors, parts tables), Anthropic API (via `email_generator` on job creation), NHTSA/VIN cache (via `decode_vin`).

**What calls it:** Frontend `api/procurement.ts` — all job lifecycle actions.
