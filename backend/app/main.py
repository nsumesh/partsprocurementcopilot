import asyncio
import contextlib
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import orders, search, vin
from app.api.procurement import router as procurement_router
from app.api.vendors import router as vendors_router
from app.config import get_settings
from app.db.sqlite_fts import FTSIndex
from app.db.supabase import get_client
from app.workers.job_processor import job_processor_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    supabase = await get_client(settings)
    fts = FTSIndex(settings.sqlite_fts_path)
    await fts.rebuild_if_missing(supabase)
    app.state.fts = fts
    app.state.supabase = supabase
    worker_task = asyncio.create_task(job_processor_loop(app.state))
    app.state.worker_task = worker_task
    yield
    worker_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await worker_task


app = FastAPI(title="Parts Procurement Copilot", lifespan=lifespan)

_settings = get_settings()
_origins = (
    ["*"]
    if _settings.cors_origins.strip() == "*"
    else [o.strip() for o in _settings.cors_origins.split(",") if o.strip()]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory per-IP sliding window; adequate for the single-process deployment
_rate_buckets: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    limit = get_settings().rate_limit_per_minute
    if limit > 0 and request.method == "POST":
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        bucket = _rate_buckets[ip]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= limit:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
        bucket.append(now)
    return await call_next(request)


@app.middleware("http")
async def api_key_guard(request: Request, call_next):
    required_key = get_settings().api_key
    if (
        required_key
        and request.url.path != "/health"
        and request.method != "OPTIONS"
        and request.headers.get("x-api-key") != required_key
    ):
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
    return await call_next(request)


app.include_router(vin.router)
app.include_router(search.router)
app.include_router(orders.router)
app.include_router(vendors_router)
app.include_router(procurement_router)


@app.get("/health")
async def health():
    # A dead worker means procurement jobs silently freeze — surface it so the
    # platform healthcheck restarts the instance instead of keeping it in rotation
    worker = getattr(app.state, "worker_task", None)
    worker_alive = worker is not None and not worker.done()
    if not worker_alive:
        return JSONResponse(
            status_code=503, content={"status": "degraded", "worker": "dead"}
        )
    return {"status": "ok", "worker": "alive"}
