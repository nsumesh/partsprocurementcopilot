import asyncio
import logging

from anthropic import AsyncAnthropic

from app.agents.email_parser import parse_vendor_response
from app.agents.followup_generator import generate_followup_email
from app.agents.ranker import compute_ranking_score
from app.agents.response_simulator import simulate_vendor_response
from app.config import get_settings
from app.db.supabase import (
    fetch_confirmed_unranked,
    fetch_pending_simulations,
    fetch_vendor_part,
    insert_procurement_event,
    update_procurement_job,
)

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 30


async def job_processor_loop(app_state) -> None:
    settings = get_settings()
    anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)
    client = app_state.supabase

    while True:
        await asyncio.sleep(_POLL_INTERVAL)
        try:
            await _process_pending_simulations(client, anthropic)
            await _process_confirmed_unranked(client)
        except Exception:
            logger.exception("Worker cycle error")


async def _process_pending_simulations(client, anthropic: AsyncAnthropic) -> None:
    jobs = await fetch_pending_simulations(client)
    for job in jobs:
        try:
            await _run_simulation(client, anthropic, job)
        except Exception:
            logger.exception("Simulation failed for job %s", job.get("id"))
            await insert_procurement_event(client, {
                "job_id": job["id"],
                "from_status": job["status"],
                "to_status": job["status"],
                "actor": "worker",
                "metadata": {"error": "simulation_failed"},
            })


async def _run_simulation(client, anthropic: AsyncAnthropic, job: dict) -> None:
    vendor = job.get("vendor") or {}
    vendor_part = await fetch_vendor_part(client, job["vendor_id"], job["part_id"]) or {}
    prev_status = job["status"]

    response_email = await simulate_vendor_response(job, vendor, vendor_part, anthropic)
    parsed = await parse_vendor_response(response_email, anthropic)

    missing = parsed.get("missing_fields") or []

    delivery_hours = vendor_part.get("delivery_hours")
    base_fields = {
        "response_email": response_email,
        "parsed_availability": parsed.get("availability_status"),
        "parsed_unit_price": parsed.get("unit_price"),
        "parsed_quantity_available": parsed.get("quantity_available"),
        "parsed_delivery_date": parsed.get("estimated_delivery_date"),
        "parsed_delivery_hours": delivery_hours,
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
        await update_procurement_job(client, job["id"], {
            **base_fields,
            "status": new_status,
            "follow_up_email": follow_up_email,
        })
    else:
        new_status = "confirmed"
        await update_procurement_job(client, job["id"], {
            **base_fields,
            "status": new_status,
        })

    await insert_procurement_event(client, {
        "job_id": job["id"],
        "from_status": prev_status,
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

    if unit_price is None or delivery_hours is None:
        return

    score = compute_ranking_score(
        unit_price=float(unit_price),
        delivery_hours=int(delivery_hours),
        response_rate=response_rate,
    )

    await update_procurement_job(client, job["id"], {
        "status": "ranked",
        "ranking_score": score,
    })

    await insert_procurement_event(client, {
        "job_id": job["id"],
        "from_status": "confirmed",
        "to_status": "ranked",
        "actor": "worker",
        "metadata": {"ranking_score": score},
    })
