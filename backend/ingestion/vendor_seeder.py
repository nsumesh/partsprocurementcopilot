import asyncio
import random
import re

from supabase import AsyncClient

from app.config import get_settings
from app.db.supabase import fetch_all_parts, get_client

VENDORS = [
    {
        "name": "FleetPride",
        "email": "parts@fleetpride.com",
        "region": "National",
        "type": "Aftermarket Distributor",
        "brands_carried": ["Multi-brand"],
        "response_rate": 0.85,
    },
    {
        "name": "Inland Truck Parts",
        "email": "parts@inlandtruckparts.com",
        "region": "Midwest / Central",
        "type": "Aftermarket Distributor",
        "brands_carried": ["Multi-brand"],
        "response_rate": 0.78,
    },
    {
        "name": "PACCAR Parts",
        "email": "parts@paccarparts.com",
        "region": "National",
        "type": "OE Distributor",
        "brands_carried": ["Kenworth", "Peterbilt"],
        "response_rate": 0.90,
    },
    {
        "name": "Meritor",
        "email": "parts@meritor.com",
        "region": "National",
        "type": "OE Manufacturer",
        "brands_carried": ["Meritor OEM"],
        "response_rate": 0.88,
    },
    {
        "name": "Bendix",
        "email": "parts@bendix.com",
        "region": "National",
        "type": "OE Manufacturer",
        "brands_carried": ["Bendix OEM"],
        "response_rate": 0.86,
    },
    {
        "name": "Haldex",
        "email": "parts@haldex.com",
        "region": "National",
        "type": "Aftermarket",
        "brands_carried": ["Haldex OEM"],
        "response_rate": 0.80,
    },
    {
        "name": "Rush Truck Centers",
        "email": "parts@rushtruckcenters.com",
        "region": "National",
        "type": "Aftermarket",
        "brands_carried": ["Peterbilt", "International"],
        "response_rate": 0.82,
    },
    {
        "name": "TravelCenters of America",
        "email": "parts@ta-petro.com",
        "region": "National",
        "type": "OE",
        "brands_carried": ["Multi-brand"],
        "response_rate": 0.65,
    },
    {
        "name": "Speedco",
        "email": "parts@speedco.com",
        "region": "National",
        "type": "OE",
        "brands_carried": ["Multi-brand"],
        "response_rate": 0.70,
    },
    {
        "name": "Action Truck Parts",
        "email": "parts@actiontruckparts.com",
        "region": "Northeast",
        "type": "Regional Aftermarket",
        "brands_carried": ["Multi-brand"],
        "response_rate": 0.75,
    },
]

_OE_TYPES = {"OE Distributor", "OE Manufacturer", "OE"}
_AFTERMARKET_TYPES = {"Aftermarket Distributor", "Aftermarket", "Regional Aftermarket"}

_DELIVERY_OPTIONS = [
    ("2 hours", 2),
    ("Next business day", 24),
    ("3-5 business days", 96),
    ("1 week", 168),
    ("8-10 days", 216),
    ("2 weeks", 336),
    ("~20 days", 480),
]


async def seed_vendors(client: AsyncClient) -> list[dict]:
    await client.table("vendors").upsert(VENDORS, on_conflict="name").execute()
    response = await client.table("vendors").select("*").execute()
    vendors = response.data or []
    print(f"  Vendors seeded: {len(vendors)}")
    return vendors


async def seed_vendor_parts(client: AsyncClient) -> None:
    parts = await fetch_all_parts(client)
    if not parts:
        print("  No parts found — run ingestion/loader.py first")
        return

    response = await client.table("vendors").select("*").execute()
    vendors = response.data or []
    if not vendors:
        print("  No vendors found — run seed_vendors first")
        return

    oe_vendors = [v for v in vendors if v["type"] in _OE_TYPES]
    aftermarket_vendors = [v for v in vendors if v["type"] in _AFTERMARKET_TYPES]

    rows = []
    for part in parts:
        source = part.get("source", "")
        if re.search(r'^oe$', source, re.IGNORECASE):
            pool = oe_vendors
        elif re.search(r'^aftermarket$', source, re.IGNORECASE):
            pool = aftermarket_vendors
        else:
            continue
        if not pool:
            continue

        base_price = float(part.get("price_usd") or 100.0)
        sampled = random.sample(pool, k=random.randint(2, min(5, len(pool))))
        for vendor in sampled:
            estimate, hours = random.choice(_DELIVERY_OPTIONS)
            rows.append(
                {
                    "vendor_id": vendor["id"],
                    "part_id": part["id"],
                    "list_price": round(base_price * random.uniform(0.85, 1.25), 2),
                    "delivery_estimate": estimate,
                    "delivery_hours": hours,
                    "in_stock": random.random() < 0.80,
                }
            )

    if not rows:
        return

    await client.table("vendor_parts").upsert(
        rows, on_conflict="vendor_id,part_id"
    ).execute()
    print(f"  Vendor-part mappings seeded: {len(rows)}")


async def main() -> None:
    settings = get_settings()
    client = await get_client(settings)
    await seed_vendors(client)
    await seed_vendor_parts(client)


if __name__ == "__main__":
    asyncio.run(main())
