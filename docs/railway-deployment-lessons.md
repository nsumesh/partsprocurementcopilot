# Railway Deployment Lessons

Sourced from the actual errors hit during the first production deployment of this project (2026-04-28).

---

## 1. Dashboard start command overrides Dockerfile CMD

**What happened:** The build succeeded and the container started, but immediately crashed with:
```
python: can't open file '/app/main.py': [Errno 2] No such file or directory
```
The Dockerfile CMD was `uv run uvicorn app.main:app ...` — but Railway had a custom start command (`python main.py`) set in the service dashboard that silently overrode it.

**Why it happens:** Railway's dashboard-level "Start Command" field takes precedence over the Dockerfile CMD. If you set it once and then change your Dockerfile, the dashboard setting wins and you'll never notice unless the app crashes.

**How to fix:**
- Go to Railway dashboard → service → Settings → Deploy → clear the "Start Command" field, OR
- Lock the correct command in `railway.toml` so it can't be overridden by the dashboard:
  ```toml
  [deploy]
  startCommand = "uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT"
  ```
- Prefer the `railway.toml` approach — it's version-controlled and travels with the code.

---

## 2. $PORT is not expanded in startCommand unless run through a shell

**What happened:** After adding `startCommand` to `railway.toml`, the app crashed with:
```
Error: Invalid value for '--port': '$PORT' is not a valid integer.
```

**Why it happens:** Railway's `startCommand` is executed directly (exec form), so environment variable substitution does not happen. `$PORT` is passed as a literal string to uvicorn.

**How to fix — Option A:** Wrap in `sh -c` to force shell expansion:
```toml
startCommand = "sh -c 'uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT'"
```

**How to fix — Option B:** Use shell-form CMD in your Dockerfile (no `startCommand` needed):
```dockerfile
CMD uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```
Shell-form Dockerfile CMD is always run through `/bin/sh -c`, so `${PORT:-8000}` expands correctly. The `:-8000` fallback also lets you run the container locally without setting `PORT`.

**Recommendation:** Use Option B — keep the command in the Dockerfile and don't set `startCommand` in `railway.toml` unless you need to override a dashboard setting. Fewer places to manage.

---

## 3. Running `railway up` from the wrong directory in a monorepo

**What happened:** `railway up` was run from the project root instead of from `backend/`. Railway's Railpack builder analyzed the root directory, saw `backend/`, `frontend/`, markdown files — no Python app at the root — and failed:
```
Railpack could not determine how to build the app.
```
The `backend/railway.toml` was ignored because it lives inside `backend/`, not at the analyzed root.

**Why it happens:** `railway up` uses the current working directory as the build context. In a monorepo, each service has its own subdirectory with its own Dockerfile and `railway.toml`. Running from the repo root sends the whole monorepo as context, bypassing per-service config.

**How to fix:**
- Always run `railway up` from the service's own directory:
  ```bash
  cd backend && railway up
  cd frontend && railway up
  ```
- In the Railway dashboard, set each service's **Root Directory** to `backend/` or `frontend/`. This controls what Railway pulls from GitHub on auto-deploy and what directory context is used.

**Rule of thumb:** If your `railway.toml` and `Dockerfile` are in a subdirectory, `railway up` must be run from that same subdirectory.

---

## 4. Vite environment variables must be set in Railway as build-time variables

**What happened:** The frontend deployed successfully but couldn't reach the backend. The local `frontend/.env` had `VITE_API_BASE_URL=http://localhost:8000`, which is correct for local dev but useless in production.

**Why it happens:** Vite bakes `VITE_*` env vars into the JS bundle at `npm run build` time — they are not read at runtime. The Dockerfile passes them as build ARGs:
```dockerfile
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build
```
If the ARG is not supplied at Docker build time, the bundle gets an empty string (or whatever the default is), and all API calls go nowhere.

**How to fix:**
- In the Railway dashboard → frontend service → Variables, add:
  ```
  VITE_API_BASE_URL = https://<your-backend-domain>.up.railway.app
  ```
- Do the same for `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`.
- After setting variables, trigger a redeploy — Railway must rebuild the image with the new ARGs baked in.

**Key distinction:** Backend env vars (API keys, DB URLs) are runtime vars — the process reads them when it starts. Frontend `VITE_*` vars are build-time vars — they're embedded in the JS at compile time. Treat them differently.

---

## 5. One service vs two services

**When to use one Railway service:**
- Simple backend-only API (no static frontend to serve)
- A fullstack app where the backend also serves the frontend (e.g., Next.js, Django with templates, FastAPI serving a built `dist/`)
- You want one URL and don't want to manage CORS

**When to use two Railway services (like this project):**
- Separate frontend and backend with different tech stacks (React + FastAPI)
- Different scaling needs — you might want 2× backend replicas but only 1 frontend (nginx is cheap)
- Different deployment cadences — frontend redeploys take longer (Vite build) than backend restarts
- Different resource requirements — backend needs memory for ML models; frontend is just nginx serving static files

**Tradeoffs of two services:**
- You must configure CORS on the backend to allow the frontend's Railway domain
- `VITE_API_BASE_URL` must point to the backend's domain and be baked in at build time (see mistake #4)
- Supabase Realtime from the frontend needs `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` set separately
- Two domains to manage (can alias to one custom domain later)

**For this project (FastAPI + React):** Two services is the right call. The frontend is pure static files served by nginx — no reason to bundle that into the Python container.

---

## 6. Healthcheck path must actually exist

**What happens if you get it wrong:** Railway's healthcheck polls the path repeatedly during startup. If it gets 404 every time, it marks the deployment as failed even if the app is otherwise running fine.

**For this project:** `railway.toml` sets `healthcheckPath = "/health"`. The FastAPI app must have:
```python
@app.get("/health")
async def health():
    return {"status": "ok"}
```
If you rename or remove that route, all future deploys will fail at the healthcheck stage even though the app itself is working.

**Timeout:** `healthcheckTimeout = 60` gives the app 60 seconds to respond. If your startup is slow (e.g., loading a large model, running a DB migration), increase this. A 502 during the healthcheck window is normal — Railway retries until timeout.
