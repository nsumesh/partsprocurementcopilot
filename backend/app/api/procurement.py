import random
from datetime import datetime, timedelta, timezone

from anthropic import AsyncAnthropic
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.agents.email_generator import generate_outreach_email
from app.config import Settings, get_settings
from app.db.supabase import (
    fetch_job_events,
    fetch_parts_by_ids,
    fetch_procurement_job,
    fetch_procurement_jobs,
    insert_procurement_event,
    insert_procurement_job,
    update_job_if_status,
)
from app.schemas.procurement import ProcurementJob, ProcurementJobCreate
from app.vin.decoder import decode_vin

router = APIRouter(prefix="/procurement", tags=["procurement"])


class FollowUpBody(BaseModel):
    follow_up_email: str | None = None


class SendBody(BaseModel):
    outreach_email: str | None = None


async def _fetch_job(supabase, job_id: str) -> ProcurementJob:
    row = await fetch_procurement_job(supabase, job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return ProcurementJob(**row)


async def _cas_transition(
    supabase,
    job_id: str,
    expected_status: str,
    to_status: str,
    extra_fields: dict | None = None,
    metadata: dict | None = None,
) -> None:
    """Atomically transition a job, guarding against concurrent state changes.

    The status predicate rides on the UPDATE itself, so two racing requests can't
    both pass a read-then-check guard — the loser gets a 409 with the actual status.
    """
    fields = {
        "status": to_status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **(extra_fields or {}),
    }
    updated = await update_job_if_status(supabase, job_id, expected_status, fields)
    if updated is None:
        current = await fetch_procurement_job(supabase, job_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Job not found")
        raise HTTPException(
            status_code=409,
            detail=f"Job is in status '{current['status']}', expected '{expected_status}'",
        )
    await insert_procurement_event(supabase, {
        "job_id": job_id,
        "from_status": expected_status,
        "to_status": to_status,
        "actor": "user",
        "metadata": metadata or {},
    })


def _respond_at(response_rate: float) -> datetime:
    now = datetime.now(timezone.utc)
    if response_rate >= 0.85:
        return now + timedelta(seconds=20)
    if response_rate >= 0.70:
        return now + timedelta(seconds=30)
    return now + timedelta(seconds=60)


@router.post("/jobs", response_model=ProcurementJob, status_code=201)
async def create_job(
    body: ProcurementJobCreate,
    request: Request,
    settings: Settings = Depends(get_settings),
):
    supabase = request.app.state.supabase

    parts = await fetch_parts_by_ids(supabase, [body.part_id])
    if not parts:
        raise HTTPException(status_code=404, detail="Part not found")
    part = parts[0]

    vendor_rows = await supabase.table("vendors").select("*").eq("id", body.vendor_id).execute()
    if not vendor_rows.data:
        raise HTTPException(status_code=404, detail="Vendor not found")
    vendor = vendor_rows.data[0]

    vin_spec = await decode_vin(body.vin, supabase, settings)
    vin_dict = vin_spec.model_dump() if vin_spec else {"vin": body.vin}

    anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)
    outreach_email = await generate_outreach_email(
        part, vendor, vin_dict, body.urgency,
        body.urgency_deadline, anthropic,
    )

    now = datetime.now(timezone.utc).isoformat()
    job_record = await insert_procurement_job(supabase, {
        **body.model_dump(exclude={"urgency_deadline"}),
        "urgency_deadline": body.urgency_deadline.isoformat() if body.urgency_deadline else None,
        "status": "created",
        "outreach_email": outreach_email,
        "created_at": now,
        "updated_at": now,
    })

    await insert_procurement_event(supabase, {
        "job_id": job_record["id"],
        "from_status": None,
        "to_status": "created",
        "actor": "user",
        "metadata": {},
    })

    return ProcurementJob(**job_record)


@router.get("/jobs", response_model=list[ProcurementJob])
async def list_jobs(request: Request):
    rows = await fetch_procurement_jobs(request.app.state.supabase)
    return [ProcurementJob(**r) for r in rows]


@router.get("/jobs/{job_id}", response_model=ProcurementJob)
async def get_job(job_id: str, request: Request):
    row = await fetch_procurement_job(request.app.state.supabase, job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    row["events"] = await fetch_job_events(request.app.state.supabase, job_id)
    return ProcurementJob(**row)


@router.post("/jobs/{job_id}/send", response_model=ProcurementJob)
async def send_outreach(job_id: str, request: Request, body: SendBody | None = None):
    supabase = request.app.state.supabase
    job = await fetch_procurement_job(supabase, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    vendor = job.get("vendor") or {}
    respond_at = _respond_at(float(vendor.get("response_rate", 0.75)))

    extra_fields: dict = {"respond_at": respond_at.isoformat()}
    # Persist the operator-edited email so edits made in the confirm modal aren't discarded
    if body and body.outreach_email:
        extra_fields["outreach_email"] = body.outreach_email

    await _cas_transition(
        supabase, job_id, "created", "outreach_sent",
        extra_fields=extra_fields,
        metadata={"respond_at": respond_at.isoformat()},
    )
    return await _fetch_job(supabase, job_id)


@router.post("/jobs/{job_id}/followup", response_model=ProcurementJob)
async def send_followup(job_id: str, body: FollowUpBody, request: Request):
    supabase = request.app.state.supabase
    job = await fetch_procurement_job(supabase, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    vendor = job.get("vendor") or {}
    respond_at = _respond_at(float(vendor.get("response_rate", 0.75)))

    extra_fields: dict = {"respond_at": respond_at.isoformat()}
    if body.follow_up_email:
        extra_fields["follow_up_email"] = body.follow_up_email

    await _cas_transition(
        supabase, job_id, "follow_up_required", "follow_up_sent",
        extra_fields=extra_fields,
        metadata={"respond_at": respond_at.isoformat()},
    )
    return await _fetch_job(supabase, job_id)


@router.post("/jobs/{job_id}/confirm", response_model=ProcurementJob)
async def confirm_parsed(job_id: str, request: Request):
    supabase = request.app.state.supabase
    await _cas_transition(supabase, job_id, "parsed", "confirmed")
    return await _fetch_job(supabase, job_id)


@router.post("/jobs/{job_id}/accept", response_model=ProcurementJob)
async def accept_job(job_id: str, request: Request):
    supabase = request.app.state.supabase
    await _cas_transition(supabase, job_id, "ranked", "accepted")
    return await _fetch_job(supabase, job_id)


@router.post("/jobs/{job_id}/reject", response_model=ProcurementJob)
async def reject_job(job_id: str, request: Request):
    supabase = request.app.state.supabase
    await _cas_transition(supabase, job_id, "ranked", "rejected")
    return await _fetch_job(supabase, job_id)
