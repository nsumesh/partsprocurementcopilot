import cohere
from anthropic import AsyncAnthropic
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.config import Settings, get_settings
from app.db.supabase import fetch_parts_by_ids
from app.pipeline.embed import embed_query
from app.pipeline.fitment import assign_fitment
from app.pipeline.intent import parse_intent
from app.pipeline.retrieve import retrieve
from app.pipeline.rerank import rerank
from app.pipeline.stream import sse_clarify, sse_done, sse_error, sse_part
from app.schemas.parts import Part
from app.schemas.search import SearchRequest
from app.vin.decoder import decode_vin

router = APIRouter(prefix="/search", tags=["search"])

_STANDARD_MODEL = "claude-sonnet-4-6"
_URGENT_MODEL = "claude-haiku-4-5-20251001"
_TOP_K = 10


async def _pipeline(request: SearchRequest, app_request: Request, settings: Settings):
    supabase = app_request.app.state.supabase
    fts = app_request.app.state.fts
    model = _STANDARD_MODEL if request.urgency == "standard" else _URGENT_MODEL
    co = cohere.AsyncClient(api_key=settings.cohere_api_key)
    anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)

    try:
        vin_spec = await decode_vin(request.vin, supabase, settings)
        if vin_spec is None:
            yield sse_error("VIN could not be decoded")
            return

        intent = await parse_intent(request.query, vin_spec, model, anthropic)
        if intent.is_ambiguous:
            yield sse_clarify(intent.clarifying_question or "Could you provide more detail?")
            return

        embedding = await embed_query(request.query, co)
        candidate_ids_scores = await retrieve(request.query, embedding, _TOP_K, supabase, fts)
        candidate_ids = [part_id for part_id, _ in candidate_ids_scores]

        raw_parts = await fetch_parts_by_ids(supabase, candidate_ids)
        id_to_score = dict(candidate_ids_scores)
        parts = [Part(**p) for p in raw_parts]

        reranked = await rerank(request.query, parts, co)

        for index, part in enumerate(reranked):
            fitment = await assign_fitment(part, vin_spec, model, anthropic)
            yield sse_part(index, part, fitment)

        yield sse_done()

    except Exception as exc:
        yield sse_error(str(exc))


@router.post("")
async def search(
    body: SearchRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
):
    return StreamingResponse(
        _pipeline(body, request, settings),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
