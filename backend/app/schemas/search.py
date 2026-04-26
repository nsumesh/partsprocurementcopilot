from typing import Literal

from pydantic import BaseModel

from app.schemas.parts import FitmentResult, Part


class VINSpec(BaseModel):
    vin: str
    make: str | None = None
    model: str | None = None
    year: int | None = None
    engine: str | None = None
    gvwr: str | None = None


class SearchRequest(BaseModel):
    vin: str
    query: str
    urgency: Literal["standard", "urgent"] = "standard"


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
