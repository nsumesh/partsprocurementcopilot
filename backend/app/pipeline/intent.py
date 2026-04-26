import json

from anthropic import AsyncAnthropic

from app.schemas.search import IntentResult, VINSpec

_SYSTEM = """\
You are a commercial truck parts procurement assistant.
Given a technician's natural language query and vehicle spec, extract the procurement intent.
Respond with a single JSON object — no markdown, no explanation:
{
  "part_category": "<canonical category>",
  "attributes": {"<key>": "<value>"},
  "clarifying_question": "<question or null>",
  "is_ambiguous": <true|false>
}
Set is_ambiguous=true ONLY when the query gives no recognizable part category at all —
for example "something is wrong" or "I need a part". If the query names any specific part
type (e.g. "oil filter", "slack adjuster", "brake shoe", "air filter", "water pump"),
always set is_ambiguous=false even if variants exist. Variant selection is handled downstream.
When is_ambiguous=true, set clarifying_question to a single short question."""


async def parse_intent(query: str, vin_spec: VINSpec, model: str, client: AsyncAnthropic) -> IntentResult:
    vehicle = f"{vin_spec.year or ''} {vin_spec.make or ''} {vin_spec.model or ''}".strip()
    engine = vin_spec.engine or "unknown engine"
    user_msg = f"Vehicle: {vehicle}, Engine: {engine}\nQuery: {query}"

    response = await client.messages.create(
        model=model,
        max_tokens=512,
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
        raise ValueError(f"Intent parse failed — raw response: {raw}") from exc

    return IntentResult(**parsed)
