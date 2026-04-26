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

Urgency toggle — Urgent increases search depth (higher top-k passed to retrieval and reranker) at the cost of higher latency. Standard uses default top-k. No UI-only difference — it actively changes retrieval behavior.

Orders — intent/request records only. No payment or external purchasing integration.


Design flow :

Database — Postgres from day one via Supabase free tier. pgvector extension for semantic search. BM25 via ParadeDB pg_search extension (available on Supabase paid; fallback to pg_trgm on free tier). RLS policies per table.

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
6. Post-generation validation — all returned part numbers checked against database; retry up to 2x on mismatch
7. Stream results — one SSE event per ranked part as they resolve

System prompt enforces: confidence level assignment, clarifying question logic, structured JSON output.


Scale :

~1000 users. Async with Celery and Redis. Frontend and backend deployed on Railway. Database on Supabase (Postgres, remote). Search submission returns task_id immediately; all heavy work inside Celery task. SSE streams results back to frontend as they arrive.

Use design-decisions.md as ground truth for designining product decisions here. 

Ask any clarification questions required from this plan to resolve any ambiguities. Build a plan explaining a file by file plan of how each file would be implemented, what will be used to implement, how it connects to the rest of the codebase and what services does it consist of. 

AI coding tools are used but all code should be explainable
Focus on: system design,  UI clarity, resilience, test coverage, API efficiency, code clarity
Keep modules small and single-purpose
Type hints in Python, TypeScript in React

Backend : Python 3.12, FastAPI, asyncio
Frontend : React 18 + Typescript + vite
