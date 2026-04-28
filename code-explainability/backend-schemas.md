# Backend — Schemas

## backend/app/schemas/parts.py

**What it does:** Defines the `Part` Pydantic model (canonical part record) and `FitmentResult` (confidence enum + reasoning string). `FitmentConfidence` is a str enum with four levels: High / Medium / Low / No Fitment.

**External services:** None.

**What calls it:** `schemas/search.py` imports `Part` and `FitmentResult`. Used as return types in all pipeline modules and API responses.

---

## backend/app/schemas/search.py

**What it does:** Defines request/response schemas for the search pipeline — `SearchRequest` (VIN + query + urgency), `VINSpec` (decoded vehicle attributes), `IntentResult` (parsed part category + attributes + ambiguity flag), and `SearchResultPart` (part + fitment + RRF score).

**External services:** None.

**What calls it:** `api/search.py`, `api/vin.py`, and all pipeline modules use these types as inputs and outputs.

---

## backend/app/schemas/orders.py

**What it does:** Defines `OrderCreate` (the POST body for placing an order) and `Order` (the stored record with `id` and `created_at`). Orders are intent records only — no payment fields.

**External services:** None.

**What calls it:** `api/orders.py` uses these as the request body and response type.

---

## backend/app/schemas/procurement.py

**What it does:** Pydantic models for the vendor outreach feature. Defines `JobStatus` as a Literal union of all 10 state machine states. `Vendor` models the 10 vendor records (name, email, region, type, brands, response_rate). `VendorPart` models the explicit vendor×part mapping (pricing, delivery_estimate string, delivery_hours int, in_stock). `ProcurementJobCreate` is the POST body for creating a job. `ProcurementJob` is the full snapshot model including all generated/received email text, parsed fields from the vendor response, ranking_score, and respond_at timestamp. `ProcurementEvent` models one immutable event log row (from/to status, actor, metadata).

**External services:** None.

**What calls it:** `api/vendors.py`, `api/procurement.py` (request/response types). `workers/job_processor.py` uses `JobStatus` states for transition logic.
