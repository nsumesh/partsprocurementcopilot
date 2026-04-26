# Deployment Steps — HeaviAI Procurement CoPilot

Railway monorepo deployment with two services: `api` (backend) and `frontend`.

---

## Prerequisites

- Railway CLI installed: `npm install -g @railway/cli`
- Railway account at railway.app
- GitHub repo pushed to origin/main
- All environment variable values ready (see `.env.example`)

---

## One-time setup

### 1. Login and create project

```bash
railway login
railway init
# Select "Create new project" → name it "heaviai"
```

---

### 2. Deploy the backend (api service)

```bash
cd backend
railway add
# Select "Empty Service" → name it "api"
railway up
```

Generate a public domain:
```bash
railway domain
# e.g. https://api-production-xxxx.up.railway.app
```

Set environment variables:
```bash
railway variable set SUPABASE_URL="https://<project-ref>.supabase.co"
railway variable set SUPABASE_KEY="<supabase-service-role-key>"
railway variable set ANTHROPIC_API_KEY="<anthropic-api-key>"
railway variable set COHERE_API_KEY="<cohere-api-key>"
```

Redeploy to apply the vars:
```bash
railway service redeploy
```

Verify:
```bash
curl https://api-production-xxxx.up.railway.app/health
# → {"status":"ok"}
```

---

### 3. Deploy the frontend service

```bash
cd ../frontend
railway add
# Select "Empty Service" → name it "frontend"
railway service link frontend
```

Set the backend URL (must be done **before** `railway up` — it is baked into the JS bundle at build time):
```bash
railway variable set VITE_API_BASE_URL="https://api-production-xxxx.up.railway.app"
```

Deploy:
```bash
railway up
```

Generate a public domain:
```bash
railway domain
# e.g. https://frontend-production-xxxx.up.railway.app
```

---

### 4. Connect GitHub for automatic deploys

Do this in the Railway dashboard for each service so every push to `main` triggers a rebuild.

**api service:**
1. Railway dashboard → project → click **api** service → **Settings**
2. Under **Source** → **Connect Repo** → select your GitHub repo
3. Branch: `main` | Root Directory: `backend`
4. Save

**frontend service:**
1. Click **frontend** service → **Settings**
2. Connect same repo → Branch: `main` | Root Directory: `frontend`
3. Save

---

## Redeployment (after initial setup)

For code changes — just push:
```bash
git push origin main
# Both services rebuild and redeploy automatically
```

For environment variable changes on the frontend — variable changes alone do not trigger a rebuild. Force one:
```bash
cd frontend
railway service redeploy
```

---

## Environment variables reference

### api service (backend)

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Supabase project URL (`https://<ref>.supabase.co`) |
| `SUPABASE_KEY` | Supabase service role key (not the anon key) |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `COHERE_API_KEY` | Cohere API key for embeddings and rerank |
| `BROWSERBASE_API_KEY` | Browserbase key (ingestion scraper only, not needed at runtime) |
| `BROWSERBASE_PROJECT_ID` | Browserbase project ID (ingestion only) |

### frontend service

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE_URL` | Full URL of the deployed api service — **must be set before building** |

---

## Common errors and fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `Railpack could not determine how to build` | Railway is reading the repo root instead of the service subdirectory | Set Root Directory to `backend` or `frontend` in service Settings |
| `Dockerfile does not exist` | Same as above — no Dockerfile at repo root | Set Root Directory per service |
| Healthcheck fails, app started OK | App listening on hardcoded port instead of `$PORT` | Use `${PORT:-8000}` in backend CMD; use `envsubst` in frontend nginx |
| Frontend shows blank page or API errors | `VITE_API_BASE_URL` set to `localhost:8000` | `railway variable set VITE_API_BASE_URL="https://api-domain"` then redeploy |
| Frontend API calls fail after setting correct URL | URL was set after the build ran | Redeploy frontend so Vite rebuilds with the new value baked in |
| `railway service create api` error | `create` is not a valid subcommand | Use `railway add` instead |

---

## Verification checklist

- [ ] `curl https://<api-domain>/health` returns `{"status":"ok"}`
- [ ] `curl https://<api-domain>/vin/1XKAD49X1EJ391052` returns Kenworth T680 spec
- [ ] Frontend loads at `https://<frontend-domain>`
- [ ] VIN blur shows vehicle confirmation
- [ ] Search streams part cards in real time
- [ ] DevTools Network tab shows `/search` as `text/event-stream` with incremental events
- [ ] Order placed → appears in Orders page after refresh
