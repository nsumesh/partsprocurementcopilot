import cohere

from ingestion.normalizer import CanonicalPart

_BATCH_SIZE = 96


async def batch_embed(
    parts: list[CanonicalPart],
    co: cohere.AsyncClient,
) -> list[list[float]]:
    texts = [
        " ".join(filter(None, [
            p.get("name", ""),
            p.get("description") or "",
            p.get("category", ""),
            p.get("brand") or "",
        ])).strip()
        for p in parts
    ]

    embeddings: list[list[float]] = []
    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        response = await co.embed(
            texts=batch,
            model="embed-english-v3.0",
            input_type="search_document",
        )
        embeddings.extend(response.embeddings)

    return embeddings
