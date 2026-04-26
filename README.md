# HeaviAI Procurement CoPilot

A parts procurement tool for fleet operators. Enter a VIN and a natural language description of what you need — the system identifies the right parts, assesses fitment against the vehicle, and lets you place an order in seconds.

**Live:** https://frontend-production-bc15.up.railway.app

---

## What it does

- Decodes any 17-character VIN via NHTSA to identify the exact vehicle (make, model, year, engine)
- Accepts natural language queries ("oil filter", "slack adjuster replacement", "fuel system parts")
- Runs a hybrid retrieval pipeline: pgvector semantic search + SQLite BM25 full-text search, merged with Reciprocal Rank Fusion
- Reranks candidates with Cohere and assesses fitment per part using Claude
- Streams results to the UI in real time via SSE — cards appear as they're scored
- Supports Standard (Sonnet) and Urgent (Haiku) modes — same pipeline, lower latency for urgent orders
- Client-side filters: source (OEM / Aftermarket), fitment confidence, price range, year range
- Order history persisted in Supabase

---

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Backend | FastAPI, Python 3.12, uv |
| AI | Anthropic Claude (intent parsing + fitment), Cohere (embeddings + rerank) |
| Database | Supabase (pgvector for semantic search, orders, VIN cache) |
| Search | SQLite FTS5 (BM25 full-text), pgvector (ANN semantic) |
| Deployment | Railway (two services), Docker |

---

## Repo layout

```
/
├── backend/          FastAPI app + ingestion pipeline
│   ├── app/          API routes, pipeline modules, schemas
│   ├── ingestion/    Data scraping, embedding, loading scripts
│   ├── Dockerfile
│   └── railway.toml
├── frontend/         React SPA
│   ├── src/
│   ├── Dockerfile
│   ├── nginx.conf
│   └── railway.toml
├── migrations/       Supabase SQL schema
└── .env.example      Required environment variables (no real values — see backend/.env)
```

---

## Local development

### Prerequisites
- Python 3.12, `uv`
- Node 20, `npm`
- A `.env` file in `backend/` — copy from `.env.example` and fill in real values

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

### Run ingestion (populates Supabase catalog)
```bash
cd backend
uv run python -m ingestion.loader
```

---

## Deployment

See [deployment-steps.md](./deployment-steps.md) for the full Railway deployment guide.
