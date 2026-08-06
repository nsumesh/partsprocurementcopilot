import asyncio
import logging

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
from app.schemas.parts import FitmentConfidence, FitmentResult, Part
from app.schemas.search import SearchRequest
from app.vin.decoder import decode_vin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

_STANDARD_MODEL = "claude-sonnet-4-6"
_URGENT_MODEL = "claude-haiku-4-5-20251001"
_CANDIDATE_K = 50  # retrieval depth feeding the reranker
_TOP_K = 10        # results returned to the client


async def _pipeline(request: SearchRequest, app_request: Request, settings: Settings):
    supabase = app_request.app.state.supabase
    fts = app_request.app.state.fts
    model = _STANDARD_MODEL if request.urgency == "standard" else _URGENT_MODEL
    co = cohere.AsyncClient(api_key=settings.cohere_api_key)
    anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)

    tasks: list[asyncio.Task] = []
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
        candidate_ids_scores = await retrieve(
            request.query, embedding, _CANDIDATE_K, supabase, fts
        )
        candidate_ids = [part_id for part_id, _ in candidate_ids_scores]

        raw_parts = await fetch_parts_by_ids(supabase, candidate_ids)
        id_to_score = dict(candidate_ids_scores)
        parts = [Part(**p) for p in raw_parts]
        # fetch_parts_by_ids returns arbitrary DB order — restore RRF order before reranking
        parts.sort(key=lambda p: id_to_score.get(p.id, 0.0), reverse=True)

        reranked = await rerank(request.query, parts, co, top_n=_TOP_K)

        intent_cat = intent.part_category.lower().replace("_", " ").replace("-", " ")
        category_matched = [
            p for p in reranked
            if intent_cat in p.category.lower() or p.category.lower() in intent_cat
        ]
        final_parts = (category_matched if category_matched else reranked)[:_TOP_K]

        async def _fitment(i: int, p: Part):
            try:
                return i, p, await assign_fitment(p, vin_spec, model, anthropic)
            except Exception:
                # One failed fitment call must not kill the other results
                logger.exception("Fitment failed for part %s", p.id)
                fallback = FitmentResult(
                    confidence=FitmentConfidence.LOW,
                    reasoning="Automated fitment check unavailable for this part.",
                )
                return i, p, fallback

        tasks = [asyncio.create_task(_fitment(i, p)) for i, p in enumerate(final_parts)]
        for coro in asyncio.as_completed(tasks):
            index, part, fitment = await coro
            yield sse_part(index, part, fitment)

        yield sse_done()

    except Exception:
        logger.exception("Search pipeline failed")
        yield sse_error("Search failed due to an internal error. Please try again.")
    finally:
        # Cancel in-flight fitment tasks on error or client disconnect so orphaned
        # LLM calls don't keep running (no-op for tasks that already finished)
        for task in tasks:
            task.cancel()


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
