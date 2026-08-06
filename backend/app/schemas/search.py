from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.parts import FitmentResult, Part


class VINSpec(BaseModel):
    vin: str
    make: str | None = None
    model: str | None = None
    year: int | None = None
    engine: str | None = None
    gvwr: str | None = None


class SearchRequest(BaseModel):
    vin: str = Field(min_length=1, max_length=17)
    # Bounded — the query is interpolated into LLM prompts, so an unbounded string is
    # an unbounded token cost
    query: str = Field(min_length=1, max_length=500)
    urgency: Literal["standard", "urgent"] = "standard"
    urgency_deadline: datetime | None = None


class IntentResult(BaseModel):
    part_category: str
    attributes: dict[str, str] = {}
    clarifying_question: str | None = None
    is_ambiguous: bool


class SearchResultPart(BaseModel):
    part: Part
    fitment: FitmentResult
    rrf_score: float
    rank: int
