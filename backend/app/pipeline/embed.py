import cohere


async def embed_query(text: str, co: cohere.AsyncClient) -> list[float]:
    response = await co.embed(
        texts=[text],
        model="embed-english-v3.0",
        input_type="search_query",
    )
    return response.embeddings[0]
