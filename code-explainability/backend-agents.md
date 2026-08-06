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

**What it does:** Extracts four structured fields from a vendor email using Claude Haiku: `availability_status`, `unit_price` (float), `quantity_available` (int), `estimated_delivery_date` (string). The vendor email is delimited in `<vendor_email>` tags with a system-prompt instruction to treat it as untrusted data and never follow instructions inside it. Output is validated through a `ParsedVendorEmail` Pydantic model that coerces currency strings ("$1,234.50") to floats and rejects out-of-bounds prices/quantities; the LLM's `missing_fields` list is reconciled against the actually-null values so a field can never be simultaneously "present" and null. Returns a dict. Uses the same markdown-fence-strip + `json.loads` pattern as `pipeline/intent.py`.

**External services:** Anthropic API (`claude-haiku-4-5-20251001`, temperature=0).

**What calls it:** `workers/job_processor.py` after `simulate_vendor_response` or a real follow-up response is received.

---

## backend/app/agents/followup_generator.py

**What it does:** Generates a follow-up email when the parsed vendor response is missing required fields. Passes the original outreach, the vendor's reply, and human-readable labels for each missing field to Claude Haiku. The vendor's reply is delimited in `<vendor_email>` tags and flagged in the prompt as untrusted data whose instructions must not be followed. Returns plain email body text for the operator to review and edit before sending.

**External services:** Anthropic API (`claude-haiku-4-5-20251001`, temperature=0).

**What calls it:** `workers/job_processor.py` when `parse_vendor_response` returns non-empty `missing_fields`.

---

## backend/app/agents/ranker.py

**What it does:** Pure Python. `delivery_text_to_hours()` parses free-text delivery estimates with ordered regex patterns — "within 24 hours" parses as 24 (a former pattern doubled it), ranges average out, and business days/weeks multiply to hours. `compute_ranking_score()` computes `price_score = 1 - (unit_price / max_catalog_price)` (default ceiling 1500, sitting above the ~$1,275 catalog max) and `delivery_score = 1 - (delivery_hours / 720)` (720h = 30-day ceiling), each clamped to [0, 1] individually so one negative component can't drag the composite to zero, then weights them `0.4 / 0.4 / 0.2` with `response_rate` and clamps the final score.

**External services:** None.

**What calls it:** `workers/job_processor.py` when a job transitions to `confirmed` and `ranking_score` is null.
