from supabase import AsyncClient

VIN_SEEDS = {
    "1XKAD49X1EJ391052": {
        "vin": "1XKAD49X1EJ391052",
        "make": "Kenworth",
        "model": "T680",
        "year": 2014,
        "engine": "Paccar MX-13",
        "gvwr": "80000 lb",
        "raw_vpic": {},
    },
    "3AKJGLD58FSGF7432": {
        "vin": "3AKJGLD58FSGF7432",
        "make": "Freightliner",
        "model": "Cascadia",
        "year": 2015,
        "engine": "DD15",
        "gvwr": "80000 lb",
        "raw_vpic": {},
    },
    "4V4NC9EH9EN157361": {
        "vin": "4V4NC9EH9EN157361",
        "make": "Volvo",
        "model": "VNL",
        "year": 2014,
        "engine": "D13",
        "gvwr": "80000 lb",
        "raw_vpic": {},
    },
    "1NPXGGGG8FD349872": {
        "vin": "1NPXGGGG8FD349872",
        "make": "Peterbilt",
        "model": "386",
        "year": 2015,
        "engine": "Cummins ISX15",
        "gvwr": "80000 lb",
        "raw_vpic": {},
    },
    "1M1AW07Y2GM001234": {
        "vin": "1M1AW07Y2GM001234",
        "make": "Mack",
        "model": "Pinnacle",
        "year": 2016,
        "engine": "MP8",
        "gvwr": "80000 lb",
        "raw_vpic": {},
    },
}


async def seed_vins(client: AsyncClient) -> None:
    records = list(VIN_SEEDS.values())
    await client.table("vin_cache").upsert(records, on_conflict="vin").execute()
    print(f"  VIN seeds upserted: {len(records)}")
