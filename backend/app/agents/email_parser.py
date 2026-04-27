import json

from anthropic import AsyncAnthropic

_SYSTEM = """\
You are a data extraction assistant. Parse a vendor email response and extract procurement fields.
Respond with a single JSON object — no markdown, no explanation:
{
  "availability_status": "<in stock | limited | out of stock | null>",
  "unit_price": <float or null>,
  "quantity_available": <integer or null>,
  "estimated_delivery_date": "<string or null>",
  "missing_fields": ["<field_name>", ...]
}
Set a field to null if the email does not mention it.
List any null fields by name in missing_fields.
missing_fields must be a subset of: availability_status, unit_price, quantity_available, estimated_delivery_date."""


async def parse_vendor_response(response_text: str, client: AsyncAnthropic) -> dict:
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        temperature=0,
        system=_SYSTEM,
        messages=[{"role": "user", "content": f"Vendor email:\n\n{response_text}"}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Email parse failed — raw response: {raw}") from exc

    parsed.setdefault("missing_fields", [])
    return parsed
