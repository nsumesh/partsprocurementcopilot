import re
import httpx
from supabase import AsyncClient

from app.config import Settings
from app.db.supabase import get_vin_cache, upsert_vin_cache
from app.schemas.search import VINSpec

_VIN_RE = re.compile(r'^[A-HJ-NPR-Z0-9]{17}$', re.IGNORECASE)


async def decode_vin(
    vin: str, client: AsyncClient, settings: Settings
) -> VINSpec | None:
    if not _VIN_RE.match(vin):
        return None

    cached = await get_vin_cache(client, vin)
    if cached and (cached.get("make") or cached.get("model")):
        return VINSpec(
            vin=cached["vin"],
            make=cached.get("make"),
            model=cached.get("model"),
            year=cached.get("year"),
            engine=cached.get("engine"),
            gvwr=cached.get("gvwr"),
        )

    url = f"{settings.nhtsa_api_base}/decodevinvalues/{vin}?format=json"
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return None

    # NHTSA can return "Results": [] — the .get default only covers a missing key
    result_rows = data.get("Results") or []
    results = result_rows[0] if result_rows else {}

    make = results.get("Make") or None
    model = results.get("Model") or None
    raw_year = results.get("ModelYear")
    try:
        year = int(raw_year) if raw_year is not None else None
    except (TypeError, ValueError):
        year = None

    cylinders = results.get("EngineCylinders") or ""
    displacement = results.get("DisplacementL") or ""
    engine_parts = [p for p in [cylinders and f"{cylinders}-cyl", displacement and f"{displacement}L"] if p]
    engine = " ".join(engine_parts) or None

    gvwr = results.get("GVWR") or None

    if not make and not model:
        return None

    spec = VINSpec(vin=vin, make=make, model=model, year=year, engine=engine, gvwr=gvwr)

    await upsert_vin_cache(client, {
        "vin": vin,
        "make": make,
        "model": model,
        "year": year,
        "engine": engine,
        "gvwr": gvwr,
        "raw_vpic": results,
    })

    return spec
