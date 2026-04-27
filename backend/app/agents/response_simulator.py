import random

from anthropic import AsyncAnthropic

_TONE_BY_TYPE = {
    "OE Distributor": "formal and professional corporate",
    "OE Manufacturer": "formal and professional corporate",
    "OE": "terse and brief — this vendor is a truck stop, not a parts specialist",
    "Aftermarket Distributor": "professional but casual and friendly",
    "Aftermarket": "casual and direct",
    "Regional Aftermarket": "casual regional distributor, conversational",
    "Dealer Network": "professional dealer network",
}

_FIELDS = ["availability_status", "unit_price", "quantity_available", "estimated_delivery_date"]

_SYSTEM = """\
You are simulating a vendor email response to a parts availability inquiry.
Write a realistic reply in the vendor's voice and tone.
Include only the fields you are told to include — omit any fields explicitly listed as missing.
Return only the email body — no subject line, no markdown, no explanation."""


async def simulate_vendor_response(
    job: dict,
    vendor: dict,
    vendor_part: dict,
    client: AsyncAnthropic,
) -> str:
    vendor_type = vendor.get("type", "Aftermarket Distributor")
    tone = _TONE_BY_TYPE.get(vendor_type, "professional")
    response_rate = float(vendor.get("response_rate", 0.8))
    p_missing = (1 - response_rate) * 0.6

    missing_fields = [f for f in _FIELDS if random.random() < p_missing]
    present_fields = [f for f in _FIELDS if f not in missing_fields]

    field_values = {
        "availability_status": "In stock" if vendor_part.get("in_stock") else "Limited availability",
        "unit_price": f"${vendor_part.get('list_price', 'N/A')}",
        "quantity_available": str(random.randint(1, 50)),
        "estimated_delivery_date": vendor_part.get("delivery_estimate", "3-5 business days"),
    }

    include_lines = "\n".join(
        f"- {f}: {field_values[f]}" for f in present_fields
    )
    omit_lines = ", ".join(missing_fields) if missing_fields else "none"

    user_msg = (
        f"Vendor name: {vendor.get('name')}\n"
        f"Vendor tone: {tone}\n"
        f"Original inquiry was for: {job.get('part_name')} (#{job.get('part_number')})\n"
        f"VIN: {job.get('vin')}\n\n"
        f"Include these fields in your response:\n{include_lines}\n\n"
        f"Do NOT mention or reference these fields (omit them entirely): {omit_lines}\n\n"
        "Write the vendor reply email body."
    )

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        temperature=0,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )

    return response.content[0].text.strip()
