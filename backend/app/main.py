import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    yield
    worker_task.cancel()


app = FastAPI(title="Parts Procurement Copilot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vin.router)
app.include_router(search.router)
app.include_router(orders.router)
app.include_router(vendors_router)
app.include_router(procurement_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
