from datetime import datetime

from anthropic import AsyncAnthropic

_SYSTEM = """\
You are a fleet procurement specialist writing a professional parts request email to a vendor.
Write a concise, professional email requesting part availability, unit price, quantity available,
and estimated delivery date. Include the vehicle VIN and spec for fitment confirmation.
Return only the email body — no subject line, no markdown, no explanation."""


async def generate_outreach_email(
    part: dict,
    vendor: dict,
    vin_spec: dict,
    urgency: str,
    deadline: datetime | None,
    client: AsyncAnthropic,
) -> str:
    vehicle = f"{vin_spec.get('year', '')} {vin_spec.get('make', '')} {vin_spec.get('model', '')}".strip()
    engine = vin_spec.get("engine", "unknown engine")
    urgency_line = ""
    if urgency == "urgent" and deadline:
        urgency_line = f"\nThis is an urgent request. Parts are needed by {deadline.strftime('%Y-%m-%d %H:%M')} UTC."

    user_msg = (
        f"Vendor: {vendor.get('name')}\n"
        f"Part: {part.get('name')} (Part #: {part.get('part_number')})\n"
        f"Category: {part.get('category')}\n"
        f"Vehicle: {vehicle}, Engine: {engine}\n"
        f"VIN: {vin_spec.get('vin', 'N/A')}"
        f"{urgency_line}\n\n"
        "Write the outreach email body."
    )

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        temperature=0,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )

    return response.content[0].text.strip()
