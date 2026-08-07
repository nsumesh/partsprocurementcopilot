# Backend — Setup

## backend/.python-version

**What it does:** Pins the Python version to 3.12 for the `backend/` directory. `uv` reads this file when creating the virtual environment, ensuring the correct interpreter is used locally and in CI.

**External services:** None.

**What calls it:** `uv` automatically reads it when running any `uv run` or `uv sync` command inside `backend/`.

---

## backend/pyproject.toml

**What it does:** Defines the backend Python project for `uv`. Declares all runtime dependencies (FastAPI, Supabase, Cohere, Anthropic, Playwright, Browserbase, httpx) and dev dependencies (pytest, pytest-asyncio). Also configures pytest to run in async mode and target the `tests/` directory.

**External services:** None directly — declares the packages that will be installed from PyPI.

**What calls it:** `uv sync` (install deps), `uv run` (run any backend command), Railway Dockerfile build.

---

## backend/app/config.py

**What it does:** Defines the `Settings` class using `pydantic-settings`, reading all environment variables from `.env`. Browserbase credentials default to empty strings — only `ingestion/scraper.py` needs them, so the API server boots without them. Hardening settings: `cors_origins` (comma-separated allowlist, `*` default for dev), `api_key` (optional X-API-Key guard, off when unset), and `rate_limit_per_minute` (per-IP POST limit, 0 disables). Exposes a `get_settings()` singleton via `@lru_cache` used as a FastAPI dependency throughout the app.

**External services:** None — reads local `.env` file.

**What calls it:** `app/main.py` (lifespan), `app/api/*.py` routes (via `Depends(get_settings)`), `app/vin/decoder.py`, ingestion scripts.

---

## backend/.env.example

**What it does:** Sanitized environment template for the backend. Documents the Supabase, Anthropic, and Cohere keys, the optional Browserbase credentials (ingestion only), and the security settings (`CORS_ORIGINS`, `API_KEY`, `RATE_LIMIT_PER_MINUTE`) with placeholder values only — never real keys. Developers copy it to `backend/.env` and fill in real values; `.env` is gitignored.

**External services:** None — documentation, not executable.

**What calls it:** Read by developers at setup time; `app/config.py` (pydantic-settings) reads the resulting `.env`.

---

## backend/app/main.py

**What it does:** Creates the FastAPI application and registers five API routers (`/vin`, `/search`, `/orders`, `/vendors`, `/procurement`). CORS origins come from `settings.cors_origins` (comma-separated allowlist; `*` allows all in dev) instead of being hardcoded. Two custom middlewares: an in-memory per-IP sliding-window rate limit on POST requests (429 over `rate_limit_per_minute`) and an optional `X-API-Key` guard on every route except `/health` when `settings.api_key` is set. On startup, initialises the Supabase client, rebuilds the SQLite FTS index if missing or empty, and starts `job_processor_loop` as an `asyncio.create_task` stored on `app.state.worker_task`; on shutdown the task is cancelled and awaited. `/health` returns 503 `degraded` when the worker task is dead so the platform healthcheck restarts the instance instead of keeping it in rotation.

**External services:** Supabase (via `db/supabase.py`), SQLite FTS (via `db/sqlite_fts.py`). Worker task connects to Supabase and Anthropic internally.

**What calls it:** `uvicorn app.main:app` — the entry point for the backend service.
