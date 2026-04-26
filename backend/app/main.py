from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import orders, search, vin
from app.config import get_settings
from app.db.sqlite_fts import FTSIndex
from app.db.supabase import get_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    supabase = await get_client(settings)
    fts = FTSIndex(settings.sqlite_fts_path)
    await fts.rebuild_if_missing(supabase)
    app.state.fts = fts
    app.state.supabase = supabase
    yield


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
