import json

from anthropic import AsyncAnthropic

from app.schemas.parts import FitmentConfidence, FitmentResult, Part
from app.schemas.search import VINSpec

_SYSTEM = """\
You are a commercial truck parts fitment expert.
Given a part's details and a vehicle spec, assess whether the part fits the vehicle.
Respond with a single JSON object — no markdown, no explanation:
{
  "confidence": "<High Probability|Medium Probability|Low Probability|No Fitment>",
  "reasoning": "<one or two sentences>"
}"""


def _structured_match(part: Part, vin_spec: VINSpec) -> FitmentResult | None:
    fn = part.fit_notes
    if not fn:
        return None

    make_match = not fn.get("make") or (
        vin_spec.make and fn["make"].lower() in vin_spec.make.lower()
    )
    model_match = not fn.get("model") or (
        vin_spec.model and fn["model"].lower() in vin_spec.model.lower()
    )
    engine_match = not fn.get("engine") or (
        vin_spec.engine and fn["engine"].lower() in vin_spec.engine.lower()
    )

    year_match = True
    yr = vin_spec.year
    if yr and fn.get("year_range"):
        yr_range = fn["year_range"]
        if isinstance(yr_range, dict):
            low = yr_range.get("min", 0)
            high = yr_range.get("max", 9999)
        elif isinstance(yr_range, str):
            # Aftermarket data stores year_range as "2005-2023" string
            parts_yr = yr_range.split("-")
            try:
                low = int(parts_yr[0])
                high = int(parts_yr[1]) if len(parts_yr) > 1 else 9999
            except (ValueError, IndexError):
                low, high = 0, 9999
        else:
            low, high = 0, 9999
        year_match = low <= yr <= high

    if make_match and model_match and engine_match and year_match:
        return FitmentResult(
            confidence=FitmentConfidence.HIGH,
            reasoning="Structured fit_notes match",
        )
    return None


async def assign_fitment(part: Part, vin_spec: VINSpec, model: str, client: AsyncAnthropic) -> FitmentResult:
    result = _structured_match(part, vin_spec)
    if result:
        return result

    vehicle = f"{vin_spec.year or ''} {vin_spec.make or ''} {vin_spec.model or ''}".strip()
    user_msg = (
        f"Part: {part.name} ({part.part_number}), Category: {part.category}, "
        f"Brand: {part.brand or 'unknown'}\n"
        f"Vehicle: {vehicle}, Engine: {vin_spec.engine or 'unknown'}\n"
        f"Fit notes: {json.dumps(part.fit_notes)}"
    )

    response = await client.messages.create(
        model=model,
        max_tokens=256,
        temperature=0,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown code fences if the model wraps its output
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Fitment parse failed — raw response: {raw}") from exc

    return FitmentResult(**parsed)
