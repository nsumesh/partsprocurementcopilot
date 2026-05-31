# Procurement CoPilot

An AI-powered parts procurement tool for heavy-duty fleet operators. Enter a VIN and a natural language description of what you need — the system finds the right parts, assesses fitment, surfaces vendors, and runs a complete AI-driven outreach loop to get quotes, parse responses, and rank vendors automatically.

**Live:** https://frontend-production-bc15.up.railway.app

(Deployment inactive at the moment, however railway files exist for deployment at any point)
---

## What it does

### Parts search
- Decodes any 17-character VIN via NHTSA to identify the exact vehicle (make, model, year, engine). Rejects malformed VINs before hitting the API (length, character set, I/O/Q exclusion).
- Accepts natural language queries ("oil filter", "slack adjuster replacement", "front axle seal")
- Hybrid retrieval: pgvector semantic search + SQLite BM25 full-text, merged with Reciprocal Rank Fusion
- Reranks candidates with Cohere Rerank, then assesses fitment per part using Claude
- Streams results to the UI in real time via SSE — cards appear as they're scored
- Standard and Urgent modes (urgency flows through the entire pipeline into outreach)
- Client-side filters: source (OEM / Aftermarket), fitment confidence, price range, year range
- Clarifying question flow: if the intent is ambiguous, the AI asks a follow-up and re-searches inline without leaving the results page

### Vendor outreach (new)
- Vendor catalog seeded from 10 real heavy-duty parts suppliers, matched to parts by source type (OE vendors → OE parts, Aftermarket vendors → Aftermarket parts)
- Operator selects a vendor from a scored list showing response rate, ETA, and price — vendors that can't meet an urgent deadline are visually dimmed
- AI (Claude Haiku) generates a professional outreach email tailored to the vendor type, part, VIN spec, and urgency deadline
- Operator reviews and edits the email before sending
- Worker loop (30s poll) simulates vendor responses with realistic voice and probabilistic field omissions based on response rate
- Parses the vendor reply and detects missing fields (price, availability, quantity, delivery date)
- Generates targeted follow-up email if fields are missing; re-parses on follow-up response
- Ranks confirmed quotes using a composite score: 40% price + 40% delivery speed + 20% response rate
- Delivery speed handles both integer hours from the vendor catalog and free-text strings ("20 days", "3-5 business days", "next business day") — ceiling at 30 days so worst-case options still contribute
- Operator accepts or rejects the ranked quote from the procurement board
- Procurement board updates in real time via Supabase Realtime (WebSocket) — no page refresh needed

---

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Backend | FastAPI, Python 3.12, uv |
| AI | Anthropic Claude Haiku (email generation, response simulation, parsing, follow-up) + Claude Sonnet (search intent, fitment) |
| Rerank | Cohere Rerank |
| Database | Supabase Postgres (pgvector, orders, VIN cache, procurement jobs + events) |
| Realtime | Supabase Realtime (WebSocket subscription on `procurement_jobs`) |
| Search | SQLite FTS5 (BM25) + pgvector (ANN) |
| Deployment | Railway (two services), Docker, nginx |

---

## Repo layout

```
/
├── backend/
│   ├── app/
│   │   ├── agents/         email_generator, response_simulator, email_parser,
│   │   │                   followup_generator, ranker
│   │   ├── api/            search, vin, orders, vendors, procurement
│   │   ├── db/             supabase.py, sqlite_fts.py
│   │   ├── pipeline/       intent, retrieval, rerank, fitment
│   │   ├── workers/        job_processor (procurement loop)
│   │   ├── schemas/        parts, orders, procurement
│   │   └── main.py
│   ├── ingestion/          loader, vendor_seeder, scraper, embedder, vin_seeds
│   ├── Dockerfile
│   └── railway.toml
├── frontend/
│   ├── src/
│   │   ├── pages/          SearchPage, ResultsPage, OrdersPage, ProcurementBoard
│   │   ├── components/     SearchBar, PartCard, PartDetail, OrderConfirm,
│   │   │                   VendorSelector, OutreachConfirm, VendorOutreachPanel,
│   │   │                   ProcurementJobRow, FilterPanel, OrderHistory
│   │   ├── api/            search, vin, orders, vendors, procurement, client
│   │   └── types/
│   ├── Dockerfile
│   ├── nginx.conf
│   └── railway.toml
├── migrations/
│   ├── 001_initial.sql     parts, orders, vin_cache, embeddings
│   └── 002_vendor_outreach.sql  vendors, vendor_parts, procurement_jobs, procurement_events
└── deployment-steps.md
```

---

## Procurement job state machine

```
created → outreach_sent → response_received → parsed
                                                  ├── confirmed → ranked → accepted
                                                  └── follow_up_required → follow_up_sent → (loops back)
                                                                                          └── rejected
```

Respond-at delays (set when transitioning to `outreach_sent` or `follow_up_sent`):

| Vendor response rate | Simulated delay |
|---|---|
| ≥ 0.85 | 20 seconds |
| 0.70 – 0.84 | 30 seconds |
| < 0.70 | 60 seconds |

---

## Local development

### Prerequisites
- Python 3.12, `uv`
- Node 20, `npm`
- Supabase project with migrations applied and Realtime enabled on `procurement_jobs`
- A `.env` file in `backend/` and `frontend/` (see env var reference below)

### Backend
```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
# API at http://localhost:8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# UI at http://localhost:5173
```

### Run ingestion (populates Supabase catalog + vendor seed)
```bash
cd backend
uv run python -m ingestion.loader
```

---

## Environment variables

### Backend (`backend/.env`)

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase **service role** key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `COHERE_API_KEY` | Cohere API key |
| `BROWSERBASE_API_KEY` | Browserbase key (ingestion scraper only) |
| `BROWSERBASE_PROJECT_ID` | Browserbase project ID (ingestion only) |

### Frontend (`frontend/.env`)

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE_URL` | Backend URL — baked into bundle at build time |
| `VITE_SUPABASE_URL` | Supabase project URL — for Realtime subscription |
| `VITE_SUPABASE_ANON_KEY` | Supabase **anon/public** key |

---

## Deployment

See [deployment-steps.md](./deployment-steps.md) for the full Railway deployment guide including build arg configuration for the frontend Docker build.
