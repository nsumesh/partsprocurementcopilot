from enum import Enum

from pydantic import BaseModel


class FitmentConfidence(str, Enum):
    HIGH = "High Probability"
    MEDIUM = "Medium Probability"
    LOW = "Low Probability"
    NONE = "No Fitment"


class Part(BaseModel):
    id: str
    part_number: str
    name: str
    description: str | None = None
    category: str
    source: str
    brand: str | None = None
    price_usd: float | None = None
    fit_notes: dict = {}
    attributes: dict = {}
    vendor_urls: list[dict] = []


class FitmentResult(BaseModel):
    confidence: FitmentConfidence
    reasoning: str
