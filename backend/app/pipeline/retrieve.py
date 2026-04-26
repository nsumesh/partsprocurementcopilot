import asyncio

from supabase import AsyncClient

from app.db.sqlite_fts import FTSIndex
from app.db.supabase import vector_search

_RRF_K = 60


async def retrieve(
    query_text: str,
    query_embedding: list[float],
    top_k: int,
    client: AsyncClient,
    fts: FTSIndex,
) -> list[tuple[str, float]]:
    loop = asyncio.get_event_loop()

    vec_task = vector_search(client, query_embedding, top_k)
    fts_task = loop.run_in_executor(None, fts.query, query_text, top_k)

    vec_results, bm25_results = await asyncio.gather(vec_task, fts_task)

    scores: dict[str, float] = {}

    for rank, row in enumerate(vec_results, start=1):
        part_id = str(row["id"])
        scores[part_id] = scores.get(part_id, 0.0) + 1.0 / (_RRF_K + rank)

    for rank, (part_id, _bm25) in enumerate(bm25_results, start=1):
        scores[part_id] = scores.get(part_id, 0.0) + 1.0 / (_RRF_K + rank)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ranked[:top_k]
