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
