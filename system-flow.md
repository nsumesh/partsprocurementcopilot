Build a system that accepts a natural language parts request and a VIN, discovers fitment-valid parts across multiple catalog sources, and surfaces ranked procurement options to a fleet operator in a clean, usable UI.


Data sources :

OE parts catalog — scraped from finditparts.com via public scrape using Browserbase. No login required.

Aftermarket parts — generated synthetically by LLM after OE catalog extraction. Aftermarket SKUs represent replacement parts not made by the original manufacturer (third-party brands, generic equivalents) for the same part categories found in the OE catalog. Stored as a CSV then ingested alongside OE data.

VIN API — NHTSA VPIC API (free, public). Covers all US commercial truck VINs including the five eval VINs. Fallback: pre-decoded local records for the eval VINs stored in the database at ingestion time.


Evals — Golden Eval Queries. Five queries with known correct answers derived from the ingested catalog:
VIN 1XKAD49X1EJ391052 — "I need an oil filter" — Paccar MX-13 oil filter, confirmed fitment
VIN 3AKJGLD58FSGF7432 — "fuel water separator for my truck" — DD15 compatible fuel water separator, confirmed fitment
VIN 4V4NC9EH9EN157361 — "radiator" — query is ambiguous, system should ask a clarifying question before returning results
VIN 1NPXGGGG8FD349872 — "slack adjuster" — aftermarket auto slack adjuster, probable fitment
VIN 1M1AW07Y2GM001234 — "serpentine belt" — MP8 compatible belt from OE catalog, confirmed fitment

Eval runner — CLI script only. No admin UI. Script runs all five queries through the live pipeline and prints per-query metrics (correct part found, rank position, confidence match, clarify triggered, latency).


User journey :

Single-user tool (no authentication). User enters query with VIN input, natural language description field, and urgency toggle (Standard / Urgent) → results show potential parts as cards marked with confidence → click a card → detail panel showing physical attributes, all vendor sources, fitment assertion → click to order → order confirmation page with part details and quantity → confirm → persists as intent record → order history showing all orders.

Urgency toggle — Urgent uses claude-haiku for lower latency. Standard uses claude-sonnet for higher accuracy. Same pipeline steps for both.

Orders — intent/request records only. No payment or external purchasing integration.


Design flow :

Database — Postgres from day one via Supabase free tier. pgvector extension for semantic search. BM25 via SQLite FTS5 (in-container, rebuilt from Supabase on cold start). RLS policies per table.

Ingest — scrape OE catalog from finditparts.com via Browserbase, generate synthetic aftermarket CSV via LLM, normalize both into canonical parts table, deduplicate across sources, generate embeddings (Cohere), persist to Supabase.

Ingestion report — total records per source, records deduplicated, records flagged for review, time taken.

Fallbacks — VIN decode falls back to pre-decoded local records seeded at ingestion time. Fitment validation uses structured fit_notes match first; LLM called only when structured match is absent or ambiguous.

Fitment confidence — defined as enum: High Probability / Medium Probability / Low Probability / No Fitment. Structured match yields High; LLM strong yields Medium; LLM weak yields Low.


AI pipeline :

Given NL query and decoded VIN specification:
1. Parse intent — extract part category, attributes, clarifying question if query is ambiguous
2. Embed query — Cohere embed (query input type)
3. Retrieve — pgvector ANN + BM25 in parallel, merged via RRF
4. Rerank — Cohere Rerank (cross-encoder) on merged candidates
5. Fitment — structured fit_notes match → LLM fallback; assigns confidence enum + reasoning per part
6. Stream results — one SSE event per ranked part as they resolve

System prompt enforces: confidence level assignment, clarifying question logic, structured JSON output.


Scale :

Async with FastAPI and asyncio. Frontend and backend deployed on Railway. Database on Supabase (Postgres, remote). SSE streams results back to frontend as they arrive.

Use design-decisions.md as ground truth for all product decisions.

AI coding tools are used but all code should be explainable.
Focus on: system design, UI clarity, resilience, API efficiency, code clarity.
Keep modules small and single-purpose.
Type hints in Python, TypeScript in React.

Backend : Python 3.12, FastAPI, asyncio
Frontend : React 18 + TypeScript + Vite

---

## Feature Addition: Vendor Outreach Agent

### Overview

Extends the parts procurement flow with an AI-driven vendor outreach loop. Rather than placing a simple order intent record, the operator initiates a procurement job that contacts a specific vendor, simulates their email response, parses it with an LLM, handles missing information via follow-up, ranks the confirmed offer, and allows the operator to accept or reject.

The job board is a new screen (`/procurement`) that shows all procurement jobs with live status updates via Supabase Realtime.


### Extended User Journey

1. User enters VIN + query + urgency → results stream in as before
2. On the results page, urgency now shows a time window input if Urgent is selected (minimum 2 hours)
3. User clicks a part card → detail panel now shows vendors for that part with ETAs and response rates alongside "Create Procurement Request" (replaces "Order")
4. User selects one vendor from the list → outreach email is generated by Claude Haiku and shown in a confirmation modal (editable)
5. User confirms → procurement job created, outreach "sent", job transitions to `outreach_sent`
6. Worker loop simulates vendor response after a delay based on response rate:
   - ≥ 0.85 response rate: ~3 minutes
   - 0.70–0.85: 10–15 minutes
   - < 0.70: 20 minutes
7. Response arrives → Claude Haiku parses four fields: availability status, unit price, quantity available, estimated delivery date
8. If all fields present → job transitions to `confirmed` → ranking score computed
9. If fields missing → job transitions to `follow_up_required` → Claude Haiku generates follow-up email → user edits and confirms send → `follow_up_sent` → worker simulates follow-up response → loops back to parse
10. Once confirmed → ranking score shown (price 40%, delivery 40%, response rate 20%)
11. User accepts → `accepted` | user rejects → `rejected`


### State Machine

```
created
  └─ user confirms outreach ──→ outreach_sent
                                    └─ worker fires (respond_at passed) ──→ response_received
                                                                               └─ Haiku parses ──→ parsed
                                                                                                    ├─ all fields present ──→ confirmed ──→ ranked ──→ accepted / rejected
                                                                                                    └─ fields missing ──→ follow_up_required
                                                                                                                              └─ user confirms follow-up ──→ follow_up_sent
                                                                                                                                                               └─ worker fires ──→ response_received (loops)
```

State transitions are recorded in `procurement_events` (from_status, to_status, actor, metadata, created_at).


### New Data Model

**`vendors`** — 10 vendors from vendors.md. Fields: id, name, email, region, type, brands_carried, response_rate.

**`vendor_parts`** — explicit vendor × part mapping. Fields: id, vendor_id, part_id, list_price, delivery_estimate (raw text, mixed formats), delivery_hours (LLM-parsed integer for ranking), in_stock.

**`procurement_jobs`** — one record per job. Holds current status snapshot plus all generated/received text: outreach_email, response_email, follow_up_email, parsed fields (availability, unit_price, quantity_available, delivery_date, delivery_hours), ranking_score, urgency_deadline.

**`procurement_events`** — immutable event log. One row per state transition. Used to compute "time elapsed in current state" and "last action taken" on the job board.


### New API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/vendors/part/{part_id}` | Vendors + ETAs for a part |
| POST | `/procurement/jobs` | Create job (part + vendor + vin + urgency) |
| GET | `/procurement/jobs` | All jobs (job board) |
| GET | `/procurement/jobs/{id}` | Single job detail |
| POST | `/procurement/jobs/{id}/send` | Confirm outreach → outreach_sent |
| POST | `/procurement/jobs/{id}/followup` | Confirm follow-up → follow_up_sent |
| POST | `/procurement/jobs/{id}/accept` | Accept ranked result → accepted |
| POST | `/procurement/jobs/{id}/reject` | Reject ranked result → rejected |


### New Agent Modules

**`email_generator.py`** — Claude Haiku generates outreach email given part, vendor, VIN spec, urgency, deadline.

**`response_simulator.py`** — Claude Haiku generates simulated vendor response. Tone and format vary by vendor type. Fields randomly omitted based on `P(missing) = (1 - response_rate) × 0.6`.

**`email_parser.py`** — Claude Haiku extracts four structured fields from vendor response text: availability_status, unit_price, quantity_available, estimated_delivery_date. Returns parsed dict + list of missing fields.

**`followup_generator.py`** — Claude Haiku generates follow-up email referencing original outreach, vendor response, and specifically missing fields.

**`ranker.py`** — Pure Python. Computes composite score from parsed unit_price, parsed delivery_hours, vendor response_rate.


### Worker Loop

`backend/app/workers/job_processor.py` — async coroutine started at FastAPI lifespan. Polls Supabase every 30 seconds:
- Jobs in `outreach_sent` or `follow_up_sent` where `respond_at <= now()` → run response simulation → parse → transition state
- Jobs in `confirmed` where ranking_score is null → compute ranking score → transition to `ranked`

All state transitions write to both `procurement_jobs` (status update) and `procurement_events` (event row).


### New Frontend Screens and Components

**`/procurement`** — ProcurementBoard page. Table of all jobs with columns: part name, vendor, status badge, time elapsed in current state, last action. Rows update live via Supabase Realtime subscription. Click row → VendorOutreachPanel.

**VendorSelector** — modal shown after "Create Procurement Request" click. Lists vendors for the part with ETA, list price, response rate badge. User selects one.

**OutreachConfirm** — modal showing Haiku-generated email in editable textarea. Confirm sends outreach.

**VendorOutreachPanel** — side panel (right slide-in). Shows: vendor info, outreach email sent, response email received, parsed field table, follow-up email (if generated, editable), composite score (if ranked), Accept / Reject buttons.

**FollowUpEditor** — editable textarea within VendorOutreachPanel when job is in `follow_up_required`. Pre-filled by Haiku. User edits and confirms.


### Live Updates: Supabase Realtime

Frontend subscribes to `procurement_jobs` table via `@supabase/supabase-js`. Status changes in the DB push to all open browser tabs immediately (~100ms). Requires `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` as frontend build-time env vars.


### Ranking Formula

```
score = (0.4 × price_score) + (0.4 × delivery_score) + (0.2 × response_rate)
price_score    = 1 - (unit_price / max_catalog_price)
delivery_score = 1 - (delivery_hours / 480)   # 480h = 20-day ceiling
response_rate  = vendor.response_rate          # 0.0 – 1.0
```
