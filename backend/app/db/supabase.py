from datetime import datetime, timezone

from supabase import AsyncClient, acreate_client

from app.config import Settings

_client: AsyncClient | None = None


async def get_client(settings: Settings) -> AsyncClient:
    global _client
    if _client is None:
        _client = await acreate_client(settings.supabase_url, settings.supabase_key)
    return _client


async def fetch_parts_by_ids(client: AsyncClient, ids: list[str]) -> list[dict]:
    response = await client.table("parts").select("*").in_("id", ids).execute()
    return response.data or []


async def fetch_all_parts(client: AsyncClient) -> list[dict]:
    response = await client.table("parts").select("*").execute()
    return response.data or []


async def upsert_parts(client: AsyncClient, parts: list[dict]) -> None:
    if not parts:
        return
    await client.table("parts").upsert(parts, on_conflict="part_number,source").execute()


async def insert_order(client: AsyncClient, order: dict) -> dict:
    response = await client.table("orders").insert(order).execute()
    return response.data[0]


async def fetch_orders(client: AsyncClient) -> list[dict]:
    response = (
        await client.table("orders").select("*").order("created_at", desc=True).execute()
    )
    return response.data or []


async def get_vin_cache(client: AsyncClient, vin: str) -> dict | None:
    response = await client.table("vin_cache").select("*").eq("vin", vin).execute()
    return response.data[0] if response.data else None


async def upsert_vin_cache(client: AsyncClient, record: dict) -> None:
    await client.table("vin_cache").upsert(record, on_conflict="vin").execute()


async def vector_search(
    client: AsyncClient, embedding: list[float], top_k: int
) -> list[dict]:
    response = await client.rpc(
        "match_parts",
        {"query_embedding": embedding, "match_count": top_k},
    ).execute()
    return response.data or []


# --- Vendor Outreach ---


async def fetch_vendors_for_part(client: AsyncClient, part_id: str) -> list[dict]:
    response = (
        await client.table("vendor_parts")
        .select("*, vendor:vendors(*)")
        .eq("part_id", part_id)
        .eq("in_stock", True)
        .execute()
    )
    return response.data or []


async def insert_procurement_job(client: AsyncClient, job: dict) -> dict:
    response = await client.table("procurement_jobs").insert(job).execute()
    return response.data[0]


async def update_procurement_job(
    client: AsyncClient, job_id: str, fields: dict
) -> dict:
    response = (
        await client.table("procurement_jobs")
        .update(fields)
        .eq("id", job_id)
        .execute()
    )
    return response.data[0]


async def fetch_procurement_jobs(client: AsyncClient) -> list[dict]:
    response = (
        await client.table("procurement_jobs")
        .select("*, vendor:vendors(*)")
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


async def fetch_procurement_job(client: AsyncClient, job_id: str) -> dict | None:
    response = (
        await client.table("procurement_jobs")
        .select("*, vendor:vendors(*)")
        .eq("id", job_id)
        .execute()
    )
    return response.data[0] if response.data else None


async def fetch_pending_simulations(client: AsyncClient) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    response = (
        await client.table("procurement_jobs")
        .select("*, vendor:vendors(*)")
        .in_("status", ["outreach_sent", "follow_up_sent"])
        .lte("respond_at", now)
        .execute()
    )
    return response.data or []


async def fetch_vendor_part(
    client: AsyncClient, vendor_id: str, part_id: str
) -> dict | None:
    response = (
        await client.table("vendor_parts")
        .select("*")
        .eq("vendor_id", vendor_id)
        .eq("part_id", part_id)
        .execute()
    )
    return response.data[0] if response.data else None


async def fetch_confirmed_unranked(client: AsyncClient) -> list[dict]:
    response = (
        await client.table("procurement_jobs")
        .select("*, vendor:vendors(*)")
        .eq("status", "confirmed")
        .is_("ranking_score", "null")
        .execute()
    )
    return response.data or []


async def insert_procurement_event(client: AsyncClient, event: dict) -> dict:
    response = await client.table("procurement_events").insert(event).execute()
    return response.data[0]


async def fetch_job_events(client: AsyncClient, job_id: str) -> list[dict]:
    response = (
        await client.table("procurement_events")
        .select("*")
        .eq("job_id", job_id)
        .order("created_at", desc=False)
        .execute()
    )
    return response.data or []
