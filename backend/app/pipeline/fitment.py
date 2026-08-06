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

    # Only fields present on BOTH sides count as evidence. If fit_notes constrain a
    # field the VIN didn't decode, or carry no verifiable field at all, escalate to
    # the LLM instead of returning HIGH on zero evidence.
    checks: list[bool] = []

    for key, vehicle_value in (
        ("make", vin_spec.make),
        ("model", vin_spec.model),
        ("engine", vin_spec.engine),
    ):
        note_value = fn.get(key)
        if not note_value:
            continue
        if not vehicle_value:
            return None
        checks.append(str(note_value).lower() in vehicle_value.lower())

    if fn.get("year_range"):
        yr = vin_spec.year
        if not yr:
            return None
        yr_range = fn["year_range"]
        low: int | None = None
        high: int | None = None
        if isinstance(yr_range, dict):
            low = yr_range.get("min", 0)
            high = yr_range.get("max", 9999)
        elif isinstance(yr_range, str):
            # Aftermarket data stores year_range as "2005-2023" string
            parts_yr = yr_range.split("-")
            try:
                low = int(parts_yr[0].strip())
                second = parts_yr[1].strip() if len(parts_yr) > 1 else ""
                high = int(second) if second else 9999
            except (ValueError, IndexError):
                low = None
        if low is None or high is None:
            # Unparseable range ("2005-Present", unexpected type) — don't assume it fits
            return None
        checks.append(low <= yr <= high)

    if not checks:
        return None

    if all(checks):
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
