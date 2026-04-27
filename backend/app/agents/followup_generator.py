from anthropic import AsyncAnthropic

_SYSTEM = """\
You are a fleet procurement specialist writing a follow-up email to a vendor.
The vendor's initial response was missing some required information.
Write a polite, professional follow-up referencing the original inquiry and the vendor's reply,
and specifically requesting only the missing fields by name.
Return only the email body — no subject line, no markdown, no explanation."""

_FIELD_LABELS = {
    "availability_status": "part availability status (in stock / lead time)",
    "unit_price": "unit price",
    "quantity_available": "quantity available",
    "estimated_delivery_date": "estimated delivery date",
}


async def generate_followup_email(
    original_email: str,
    response_text: str,
    missing_fields: list[str],
    vendor: dict,
    client: AsyncAnthropic,
) -> str:
    missing_labels = "\n".join(
        f"- {_FIELD_LABELS.get(f, f)}" for f in missing_fields
    )

    user_msg = (
        f"Vendor: {vendor.get('name')}\n\n"
        f"Original outreach sent:\n{original_email}\n\n"
        f"Vendor's reply:\n{response_text}\n\n"
        f"The following required fields were not provided:\n{missing_labels}\n\n"
        "Write a brief follow-up email requesting only these missing details."
    )

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        temperature=0,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )

    return response.content[0].text.strip()
