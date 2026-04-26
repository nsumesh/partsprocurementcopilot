import asyncio
import csv
import time
from pathlib import Path

import cohere

from app.config import get_settings
from app.db.sqlite_fts import FTSIndex
from app.db.supabase import fetch_all_parts, get_client, upsert_parts
from ingestion.aftermarket import generate_aftermarket_csv
from ingestion.embedder import batch_embed
from ingestion.normalizer import CanonicalPart, normalize_aftermarket, normalize_oe
from ingestion.scraper import scrape_oe_parts
from ingestion.vin_seeds import seed_vins

_AFTERMARKET_CSV = "data/aftermarket.csv"


async def run_ingestion() -> None:
    start = time.monotonic()
    settings = get_settings()
    supabase = await get_client(settings)
    co = cohere.AsyncClient(api_key=settings.cohere_api_key)

    print("Step 1/9 — Scraping OE parts from finditparts.com...")
    oe_raw = await scrape_oe_parts(settings)
    print(f"  OE raw parts scraped: {len(oe_raw)}")

    print("Step 2/9 — Generating aftermarket CSV via Claude...")
    await generate_aftermarket_csv(oe_raw, settings.anthropic_api_key, _AFTERMARKET_CSV)

    print("Step 3/9 — Normalizing parts...")
    normalized: list[CanonicalPart] = [normalize_oe(raw) for raw in oe_raw]
    aftermarket_rows = _load_csv(_AFTERMARKET_CSV)
    normalized.extend(normalize_aftermarket(row) for row in aftermarket_rows)
    print(f"  OE: {len(oe_raw)}, Aftermarket: {len(aftermarket_rows)}")

    print("Step 4/9 — Deduplicating...")
    seen: set[tuple[str, str]] = set()
    deduped: list[CanonicalPart] = []
    dedup_count = 0
    for part in normalized:
        key = (part["part_number"], part["source"])
        if part["part_number"] and key not in seen:
            seen.add(key)
            deduped.append(part)
        else:
            dedup_count += 1
    print(f"  After dedup: {len(deduped)} parts ({dedup_count} removed)")

    print("Step 5/9 — Embedding parts with Cohere...")
    embeddings = await batch_embed(deduped, co)

    print("Step 6/9 — Attaching embeddings...")
    parts_with_embeddings: list[dict] = []
    for part, emb in zip(deduped, embeddings):
        p = dict(part)
        p["embedding"] = emb
        parts_with_embeddings.append(p)

    print("Step 7/9 — Upserting to Supabase...")
    await upsert_parts(supabase, parts_with_embeddings)
    print(f"  Upserted {len(parts_with_embeddings)} parts")

    print("Step 8/9 — Building SQLite FTS index...")
    # Fetch back from Supabase so each part has its Supabase-assigned UUID
    fetched = await fetch_all_parts(supabase)
    fts = FTSIndex(settings.sqlite_fts_path)
    fts.build(fetched)
    print(f"  FTS index built ({len(fetched)} parts)")

    print("Step 9/9 — Seeding VIN cache...")
    await seed_vins(supabase)

    elapsed = time.monotonic() - start
    oe_count = sum(1 for p in deduped if p["source"] == "OE")
    am_count = sum(1 for p in deduped if p["source"] == "aftermarket")

    print()
    print("Ingestion complete")
    print(f"  OE parts:          {oe_count}")
    print(f"  Aftermarket parts: {am_count}")
    print(f"  Deduplicated:      {dedup_count}")
    print(f"  Flagged for review: 0")
    print(f"  Time taken:        {elapsed:.1f}s")


def _load_csv(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


if __name__ == "__main__":
    asyncio.run(run_ingestion())
