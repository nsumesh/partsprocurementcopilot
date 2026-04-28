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

**What it does:** Defines the `Settings` class using `pydantic-settings`, reading all environment variables from `.env`. Exposes a `get_settings()` singleton via `@lru_cache` used as a FastAPI dependency throughout the app.

**External services:** None — reads local `.env` file.

**What calls it:** `app/main.py` (lifespan), `app/api/*.py` routes (via `Depends(get_settings)`), `app/vin/decoder.py`, ingestion scripts.

---

## backend/app/main.py

**What it does:** Creates the FastAPI application with CORS middleware and registers five API routers (`/vin`, `/search`, `/orders`, `/vendors`, `/procurement`). On startup, initialises the Supabase client, rebuilds the SQLite FTS index if missing or empty, and starts `job_processor_loop` as an `asyncio.create_task`. The task handle is cancelled cleanly on shutdown.

**External services:** Supabase (via `db/supabase.py`), SQLite FTS (via `db/sqlite_fts.py`). Worker task connects to Supabase and Anthropic internally.

**What calls it:** `uvicorn app.main:app` — the entry point for the backend service.
