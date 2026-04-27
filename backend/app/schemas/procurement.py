from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

JobStatus = Literal[
    "created",
    "outreach_sent",
    "response_received",
    "parsed",
    "follow_up_required",
    "follow_up_sent",
    "confirmed",
    "ranked",
    "accepted",
    "rejected",
]


class Vendor(BaseModel):
    id: str
    name: str
    email: str
    region: str
    type: str
    brands_carried: list[str] = []
    response_rate: float


class VendorPart(BaseModel):
    id: str
    vendor_id: str
    part_id: str
    list_price: float | None = None
    delivery_estimate: str | None = None
    delivery_hours: int | None = None
    in_stock: bool = True
    vendor: Vendor | None = None


class ProcurementJobCreate(BaseModel):
    part_id: str
    vendor_id: str
    part_number: str
    part_name: str
    vin: str
    query: str
    urgency: Literal["standard", "urgent"] = "standard"
    urgency_deadline: datetime | None = None


class ProcurementJob(BaseModel):
    id: str
    part_id: str
    vendor_id: str
    part_number: str
    part_name: str
    vin: str
    query: str
    urgency: str
    urgency_deadline: datetime | None = None
    status: JobStatus
    outreach_email: str | None = None
    response_email: str | None = None
    follow_up_email: str | None = None
    parsed_availability: str | None = None
    parsed_unit_price: float | None = None
    parsed_quantity_available: int | None = None
    parsed_delivery_date: str | None = None
    parsed_delivery_hours: int | None = None
    ranking_score: float | None = None
    respond_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None
    vendor: Vendor | None = None
    events: list["ProcurementEvent"] = []


class ProcurementEvent(BaseModel):
    id: str
    job_id: str
    from_status: str | None = None
    to_status: str
    actor: str
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
