import httpx
from supabase import AsyncClient

from app.config import Settings
from app.db.supabase import get_vin_cache, upsert_vin_cache
from app.schemas.search import VINSpec


async def decode_vin(
    vin: str, client: AsyncClient, settings: Settings
) -> VINSpec | None:
    cached = await get_vin_cache(client, vin)
    if cached:
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
    except (httpx.HTTPError, Exception):
        return None

    results = data.get("Results", [{}])[0]

    make = results.get("Make") or None
    model = results.get("Model") or None
    raw_year = results.get("ModelYear")
    year = int(raw_year) if raw_year and raw_year.isdigit() else None

    cylinders = results.get("EngineCylinders") or ""
    displacement = results.get("DisplacementL") or ""
    engine_parts = [p for p in [cylinders and f"{cylinders}-cyl", displacement and f"{displacement}L"] if p]
    engine = " ".join(engine_parts) or None

    gvwr = results.get("GVWR") or None

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
