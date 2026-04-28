# Backend — Agents

## backend/app/agents/email_generator.py

**What it does:** Generates a professional parts outreach email using Claude Haiku. Accepts the part dict, vendor dict, decoded VIN spec dict, urgency, and optional deadline. Appends an urgency line when the request is urgent and a deadline is set. Returns plain email body text — no JSON, no markdown fences expected.

**External services:** Anthropic API (`claude-haiku-4-5-20251001`, temperature=0).

**What calls it:** `api/procurement.py` (POST /procurement/jobs — generates outreach email on job creation).

---

## backend/app/agents/response_simulator.py

**What it does:** Simulates a vendor's email reply using Claude Haiku. Derives the vendor's communication tone from their `type` field (formal for OE Manufacturers, terse for OE truck-stop vendors, casual for Aftermarket). Calculates `P(field_missing) = (1 - response_rate) × 0.6` per field and randomly omits fields to exercise the follow-up path. Passes field values and omission list to Haiku so the reply is realistic but intentionally incomplete for lower-rated vendors.

**External services:** Anthropic API (`claude-haiku-4-5-20251001`, temperature=0).

**What calls it:** `workers/job_processor.py` when a job's `respond_at` passes.

---

## backend/app/agents/email_parser.py

**What it does:** Extracts four structured fields from a vendor email using Claude Haiku: `availability_status`, `unit_price` (float), `quantity_available` (int), `estimated_delivery_date` (string). Returns a dict with a `missing_fields` list for any fields that were null. Uses the same markdown-fence-strip + `json.loads` pattern as `pipeline/intent.py`.

**External services:** Anthropic API (`claude-haiku-4-5-20251001`, temperature=0).

**What calls it:** `workers/job_processor.py` after `simulate_vendor_response` or a real follow-up response is received.

---

## backend/app/agents/followup_generator.py

**What it does:** Generates a follow-up email when the parsed vendor response is missing required fields. Passes the original outreach, the vendor's reply, and human-readable labels for each missing field to Claude Haiku. Returns plain email body text for the operator to review and edit before sending.

**External services:** Anthropic API (`claude-haiku-4-5-20251001`, temperature=0).

**What calls it:** `workers/job_processor.py` when `parse_vendor_response` returns non-empty `missing_fields`.

---

## backend/app/agents/ranker.py

**What it does:** Pure Python. Computes a composite ranking score from three inputs: `price_score = 1 - (unit_price / max_catalog_price)`, `delivery_score = 1 - (delivery_hours / 480)` (480h = 20-day ceiling), weighted `0.4 / 0.4 / 0.2` with `response_rate`. Output is clamped to [0, 1].

**External services:** None.

**What calls it:** `workers/job_processor.py` when a job transitions to `confirmed` and `ranking_score` is null.
