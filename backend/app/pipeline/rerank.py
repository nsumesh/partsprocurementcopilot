import cohere

from app.schemas.parts import Part


async def rerank(query: str, parts: list[Part], co: cohere.AsyncClient) -> list[Part]:
    if not parts:
        return parts

    docs = [
        f"{p.name} {p.description or ''} {p.category} {p.brand or ''}".strip()
        for p in parts
    ]

    response = await co.rerank(
        model="rerank-english-v3.0",
        query=query,
        documents=docs,
        top_n=len(parts),
    )

    return [parts[r.index] for r in response.results]
