import asyncio
import logging
from datetime import datetime, timedelta, timezone

from anthropic import AsyncAnthropic

from app.agents.email_parser import parse_vendor_response
from app.agents.followup_generator import generate_followup_email
from app.agents.ranker import compute_ranking_score, delivery_text_to_hours, _DELIVERY_CEILING_HOURS
from app.agents.response_simulator import simulate_vendor_response
from app.config import get_settings
from app.db.supabase import (
    fetch_confirmed_unranked,
    fetch_pending_simulations,
    fetch_vendor_part,
    insert_procurement_event,
    update_job_if_status,
)

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 30
_MAX_ATTEMPTS = 3


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def job_processor_loop(app_state) -> None:
    # Initialization happens inside the loop so a transient failure (missing key,
    # network blip) degrades to a logged retry instead of silently killing the task
    # while /health keeps reporting ok.
    anthropic: AsyncAnthropic | None = None

    while True:
        await asyncio.sleep(_POLL_INTERVAL)
        try:
            if anthropic is None:
                settings = get_settings()
                anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)
            client = app_state.supabase
            await _process_pending_simulations(client, anthropic)
            await _process_confirmed_unranked(client)
        except Exception:
            logger.exception("Worker cycle error")


async def _process_pending_simulations(client, anthropic: AsyncAnthropic) -> None:
    jobs = await fetch_pending_simulations(client)
    for job in jobs:
        prev_status = job["status"]
        # Claim the job before doing any LLM work: the CAS flip to response_received
        # makes concurrent workers (or a user action racing the poll) skip it.
        claimed = await update_job_if_status(client, job["id"], prev_status, {
            "status": "response_received",
            "updated_at": _now_iso(),
        })
        if claimed is None:
            continue
        try:
            await insert_procurement_event(client, {
                "job_id": job["id"],
                "from_status": prev_status,
                "to_status": "response_received",
                "actor": "worker",
                "metadata": {},
            })
            await _run_simulation(client, anthropic, job)
        except Exception as exc:
            logger.exception("Simulation failed for job %s", job.get("id"))
            await _record_failure(client, job, prev_status, exc)


async def _record_failure(client, job: dict, prev_status: str, exc: Exception) -> None:
    attempts = (job.get("attempt_count") or 0) + 1
    error_text = f"{type(exc).__name__}: {exc}"[:500]
    # Cap retries: releasing the claim back to prev_status retries next cycle; after
    # _MAX_ATTEMPTS the job lands in the terminal 'failed' state instead of burning
    # LLM calls every 30s forever.
    new_status = "failed" if attempts >= _MAX_ATTEMPTS else prev_status
    try:
        await update_job_if_status(client, job["id"], "response_received", {
            "status": new_status,
            "attempt_count": attempts,
            "updated_at": _now_iso(),
        })
        await insert_procurement_event(client, {
            "job_id": job["id"],
            "from_status": "response_received",
            "to_status": new_status,
            "actor": "worker",
            "metadata": {"error": error_text, "attempt": attempts},
        })
    except Exception:
        # Guarded so a failing failure-handler can't abort the rest of the batch
        logger.exception("Could not record failure for job %s", job.get("id"))


async def _run_simulation(client, anthropic: AsyncAnthropic, job: dict) -> None:
    vendor = job.get("vendor") or {}
    vendor_part = await fetch_vendor_part(client, job["vendor_id"], job["part_id"]) or {}

    response_email = await simulate_vendor_response(job, vendor, vendor_part, anthropic)
    parsed = await parse_vendor_response(response_email, anthropic)

    missing = parsed.get("missing_fields") or []

    delivery_hours = vendor_part.get("delivery_hours")
    if delivery_hours is None:
        delivery_hours = delivery_text_to_hours(parsed.get("estimated_delivery_date"))
    base_fields = {
        "response_email": response_email,
        "parsed_availability": parsed.get("availability_status"),
        "parsed_unit_price": parsed.get("unit_price"),
        "parsed_quantity_available": parsed.get("quantity_available"),
        "parsed_delivery_date": parsed.get("estimated_delivery_date"),
        "parsed_delivery_hours": delivery_hours,
        "attempt_count": 0,
        "updated_at": _now_iso(),
    }

    if missing:
        follow_up_email = await generate_followup_email(
            job.get("outreach_email", ""),
            response_email,
            missing,
            vendor,
            anthropic,
        )
        new_status = "follow_up_required"
        updated = await update_job_if_status(client, job["id"], "response_received", {
            **base_fields,
            "status": new_status,
            "follow_up_email": follow_up_email,
        })
    else:
        new_status = "parsed"
        updated = await update_job_if_status(client, job["id"], "response_received", {
            **base_fields,
            "status": new_status,
        })

    if updated is None:
        logger.warning("Job %s left response_received mid-simulation — skipping", job["id"])
        return

    await insert_procurement_event(client, {
        "job_id": job["id"],
        "from_status": "response_received",
        "to_status": new_status,
        "actor": "worker",
        "metadata": {"missing_fields": missing},
    })


async def _process_confirmed_unranked(client) -> None:
    jobs = await fetch_confirmed_unranked(client)
    for job in jobs:
        try:
            await _rank_job(client, job)
        except Exception:
            logger.exception("Ranking failed for job %s", job.get("id"))


async def _rank_job(client, job: dict) -> None:
    unit_price = job.get("parsed_unit_price")
    delivery_hours = job.get("parsed_delivery_hours")
    vendor = job.get("vendor") or {}
    response_rate = float(vendor.get("response_rate", 0.75))

    if unit_price is None:
        # Fail visibly instead of leaving the job re-selected at 'confirmed' every
        # cycle forever with no trace.
        updated = await update_job_if_status(client, job["id"], "confirmed", {
            "status": "failed",
            "updated_at": _now_iso(),
        })
        if updated is not None:
            await insert_procurement_event(client, {
                "job_id": job["id"],
                "from_status": "confirmed",
                "to_status": "failed",
                "actor": "worker",
                "metadata": {"error": "missing unit_price — cannot rank"},
            })
        return

    # Fall back to parsing the delivery date text, then worst-case ceiling
    if delivery_hours is None:
        delivery_hours = delivery_text_to_hours(job.get("parsed_delivery_date"))
    if delivery_hours is None:
        delivery_hours = _DELIVERY_CEILING_HOURS

    score = compute_ranking_score(
        unit_price=float(unit_price),
        delivery_hours=int(delivery_hours),
        response_rate=response_rate,
    )

    metadata: dict = {"ranking_score": score}
    deadline_raw = job.get("urgency_deadline")
    if deadline_raw:
        try:
            deadline = datetime.fromisoformat(str(deadline_raw).replace("Z", "+00:00"))
            projected = datetime.now(timezone.utc) + timedelta(hours=int(delivery_hours))
            metadata["meets_deadline"] = projected <= deadline
        except ValueError:
            pass

    # CAS on 'confirmed' so a user accept/reject racing this cycle is never clobbered
    updated = await update_job_if_status(client, job["id"], "confirmed", {
        "status": "ranked",
        "ranking_score": score,
        "updated_at": _now_iso(),
    })
    if updated is None:
        return

    await insert_procurement_event(client, {
        "job_id": job["id"],
        "from_status": "confirmed",
        "to_status": "ranked",
        "actor": "worker",
        "metadata": metadata,
    })
