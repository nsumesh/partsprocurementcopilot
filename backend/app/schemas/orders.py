from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class OrderCreate(BaseModel):
    part_id: str
    part_number: str
    part_name: str
    quantity: int = Field(default=1, ge=1)
    vin: str | None = None
    query: str | None = None
    urgency: Literal["standard", "urgent"] = "standard"


class Order(OrderCreate):
    id: str
    created_at: datetime
