# HeaviAI Procurement CoPilot — Testing Edge Case Suite

## Overview

This document covers the full test surface: VIN decode, AI pipeline, fitment, streaming, filters, orders, load, security, and integration failures. Tests are grouped by area. Each entry includes the scenario, exact steps, expected outcome, and failure mode to watch for.

---

## How to Run

```bash
# Start backend
cd backend && uv run uvicorn app.main:app --reload   # :8000

# Start frontend
cd frontend && npm run dev                           # :5173

# Eval golden queries
cd backend && uv run python -m ingestion.eval_runner
```

---

## 1. VIN Input Tests

| ID | Scenario | Steps | Expected | Failure Mode |
|----|----------|-------|----------|--------------|
| VIN-01 | Valid seeded VIN | Enter `1XKAD49X1EJ391052`, blur | "✓ 2014 Kenworth T680 — Paccar MX-13" | No confirmation shown |
| VIN-02 | Valid non-seeded VIN | Enter a real 17-char VIN not in vin_seeds, blur | Vehicle data from NHTSA live API | Timeout or 422 if NHTSA down |
| VIN-03 | Too short | Enter `1XKAD49X1EJ391` (14 chars), blur | No API call, no confirmation | API called with short VIN |
| VIN-04 | Too long | Enter 18-char string | Input maxLength=17 prevents entry | Input accepts >17 chars |
| VIN-05 | All zeros | Enter `00000000000000000`, blur | 422 or empty VINSpec | Server crash |
| VIN-06 | Non-alphanumeric | Enter `1XKAD49X1EJ39!@#`, blur | No confirmation; VIN decode fails gracefully | Unhandled exception |
| VIN-07 | VIN decode timeout | Block NHTSA in devtools, enter valid VIN, blur | `null` returned, no confirmation shown, search still submittable | Hang/spinner forever |
| VIN-08 | Change VIN after confirmation | Confirm VIN-01, then edit VIN field | Confirmation clears immediately | Stale confirmation persists |
| VIN-09 | Clarify VIN `4V4NC9EH9EN157361` + "need brakes" | Submit | Amber clarify banner, no part cards | Part cards appear instead |, part cards appeared here, clarifying banner

---

## 2. Search Query Tests

| ID | Scenario | Steps | Expected | Failure Mode |
|----|----------|-------|----------|--------------|
| Q-01 | Empty query | Submit with no query text | Button disabled; no submit | Form submits with empty string |
| Q-02 | Whitespace-only query | Enter `"   "`, submit | Button disabled (trim check) | Backend receives whitespace |
| Q-03 | Very long query (500+ chars) | Paste 500-char description, submit | Search proceeds; intent parser truncates gracefully | 422 / LLM timeout |, banner came but canr enter any input here
| Q-04 | Special characters | Enter `oil filter <script>alert(1)</script>`, submit | Characters passed as plain text to LLM; no XSS | Script tag executed in UI |, script tag got executed in UI
| Q-05 | SQL injection in query | Enter `'; DROP TABLE parts; --`, submit | Treated as natural language; no DB modification | DB error / data loss |
| Q-06 | Non-English query | Enter "filtro de aceite" (Spanish), submit | Intent parser extracts oil filter category or returns ambiguous | 500 error |, returned all low fit or no fir cards
| Q-07 | Category with no DB results | Enter "landing gear parts", submit | `[DONE]` with 0 results; "No parts found" empty state | Spinner hangs |, returned 10 results
| Q-08 | Fully unrecognizable query | Enter "something is broken on my truck", submit | Clarify banner with a clarifying question | Part results returned |
| Q-09 | Named part + variant | Enter "slack adjuster", submit | `is_ambiguous=false`; results stream | Clarify banner appears | clarfying banner appeared
| Q-10 | Exact part number | Enter part number from catalog, submit | Top result matches that part | No match found |

---

## 3. AI Pipeline / Intent Tests

| ID | Scenario | Steps | Expected | Failure Mode |
|----|----------|-------|----------|--------------|
| AI-01 | Standard urgency uses Sonnet | Submit with Standard | Server log: `model=claude-sonnet-4-6` | Haiku used for standard |
| AI-02 | Urgent urgency uses Haiku | Submit with Urgent | Server log: `model=claude-haiku-4-5-20251001` | Sonnet used for urgent |
| AI-03 | Haiku JSON fence stripping | Any urgent query | Valid JSON parsed; no `JSONDecodeError` | `json.loads` raises exception on ` ```json ``` ` output |
| AI-04 | LLM returns unexpected field | Kill API mid-intent parse | Graceful SSE error event; frontend shows error banner | Unhandled Python exception |
| AI-05 | Anthropic rate limit | Rapidly submit 10+ concurrent searches | 429 handled; SSE error event returned | Server 500 or hang |
| AI-06 | Cohere embed failure | Revoke Cohere API key temporarily | Graceful SSE error event; meaningful message | Traceback in SSE stream |
| AI-07 | Cohere rerank failure | Revoke Cohere API key post-retrieval | Graceful error or fallback order | Silent empty results |
| AI-08 | Anthropic key not set | Remove `ANTHROPIC_API_KEY` from .env, restart | Server startup error logged clearly; 500 returned | Silent auth failure |

---

## 4. Fitment Tests

| ID | Scenario | Steps | Expected | Failure Mode |
|----|----------|-------|----------|--------------|
| FIT-01 | Full structured match | Part with matching make/model/engine in `fit_notes` | `High Probability` without LLM call | LLM called unnecessarily |
| FIT-02 | Year range mismatch (dict) | Part with `year_range: {"min": 2000, "max": 2010}`, truck is 2015 | `Low Probability` or `No Fitment` | `High Probability` assigned |
| FIT-03 | Year range mismatch (string) | Part with `year_range: "2000-2010"`, truck is 2015 | Same as FIT-02; `isinstance` guard handles string | `AttributeError: 'str' has no .get` |
| FIT-04 | Empty `fit_notes` | Part with `fit_notes: {}` | LLM fallback runs; result based on name/description | Exception on empty dict |
| FIT-05 | Universal part | Part with no make/model in `fit_notes`, e.g. generic oil filter | LLM returns `Medium Probability` or `High Probability` with appropriate reasoning | `No Fitment` returned |
| FIT-06 | Wrong make | 2014 Kenworth T680 VIN + Freightliner-specific part | `Low Probability` or `No Fitment` | `High Probability` returned |
| FIT-07 | LLM fitment JSON fence | Urgent mode (Haiku) fitment response | Fences stripped; no `JSONDecodeError` | Parse error in fitment |
| FIT-08 | Invalid confidence value from LLM | LLM returns `"Very High Probability"` | Caught by Pydantic validation; default to `Low Probability` or error | Unhandled `ValidationError` |

---

## 5. Streaming / SSE Tests

| ID | Scenario | Steps | Expected | Failure Mode |
|----|----------|-------|----------|--------------|
| SSE-01 | Cards arrive incrementally | Submit search | Each card fades in as its `data:` event arrives; not all at once | All cards appear at same time (buffering) | arrives incrementally
| SSE-02 | Navigate away during stream | Submit, then click "← Back" within 2 seconds | `AbortController.abort()` fires; stream stops; no state updates after unmount | Continued SSE parsing after navigate |. no update
| SSE-03 | New search cancels previous | Submit two searches in quick succession from ResultsPage (use browser back/forward) | Second search only | Two streams merged in UI |, second search
| SSE-04 | Network drop mid-stream | Throttle network to offline after first card | Cards received before drop retained; error banner for incomplete stream | Spinner hangs forever |, spinner hangs
| SSE-05 | Backend crashes mid-stream | Kill uvicorn after 3 parts streamed | Error event or stream closes; frontend shows received parts + error banner | Frontend freezes | network error shown, format error just as network error or lost connectivity instead of showing type erro
| SSE-06 | `[DONE]` event | Complete a full search | `isStreaming` becomes `false`; dot-bounce disappears | Streaming indicator stays on |
| SSE-07 | Empty result stream | Query with no catalog matches | `[DONE]` immediately; empty state rendered | Spinner never stops |
| SSE-08 | Malformed SSE line | Inject garbage between `data:` lines in test | Malformed lines skipped silently | `JSON.parse` exception crashes handler |

---

## 6. Filter Tests

| ID | Scenario | Steps | Expected | Failure Mode |
|----|----------|-------|----------|--------------|
| F-01 | Filter by OEM only | Check "OEM" source | Only OEM parts shown | Aftermarket parts still visible |, only OEM shown
| F-02 | Filter by Aftermarket only | Check "Aftermarket" source | Only aftermarket parts shown | OEM parts still visible |only aftermarket
| F-03 | Filter by High fitment | Check "High" confidence | Only High Probability parts shown | Lower confidence parts remain | works
| F-04 | Price min > all parts | Enter min price higher than any part | 0 results; "No parts match filters" + clear button | Spinner or crash | works
| F-05 | Price max = 0 | Enter max price 0 | Parts with `price_usd = 0` or `null` shown (null not excluded by max) | All results filtered out | works
| F-06 | All parts have null price | Set any price filter on a catalog with no prices | All parts hidden; not treated as $0 | Null prices treated as $0 | sorks
| F-07 | Year range out of catalog bounds | Enter 2030–2040 | All parts filtered out (no parts fit those years) | Results unchanged | results show
| F-08 | Year range string format | Parts with `year_range: "2005-2023"` | String parsed correctly by `extractYearRange` | `NaN` comparison silently passes all | works
| F-09 | Stacking multiple filters | Check OEM + High + price 0–200 | Intersection of all three applied | OR logic instead of AND | works
| F-10 | Clear all filters | Apply filters, click "Clear all" | `DEFAULT_FILTERS` restored; all parts shown | Partial filter remains | works
| F-11 | Filter during streaming | Apply filter while SSE is still incoming | New cards evaluated against current filters as they arrive | Filters not applied to new cards | works

---

## 7. Order Flow Tests

| ID | Scenario | Steps | Expected | Failure Mode |
|----|----------|-------|----------|--------------|
| O-01 | Standard order | Click part → Order → quantity=1 → Confirm | Redirect to `/orders`; order appears in table | No redirect; order not saved | works
| O-02 | Quantity = 1 (minimum) | Set quantity to 1 | Order created with qty=1 | Input allows 0 |works
| O-03 | Quantity = 0 (prevented) | Try to enter 0 | Input coerces to 1 (`Math.max(1, ...)`) | qty=0 sent to backend |works
| O-04 | Large quantity | Enter 999 | Order created with qty=999; total price shown correctly | Validation error or overflow |works
| O-05 | Total price calculation | qty=3, part price=$45.00 | Total shows $135.00 in confirm modal | Wrong calculation |works
| O-06 | Part with no price | Order a part where `price_usd = null` | Price and total rows hidden; order still submits | Error or "$NaN" shown |works
| O-07 | Cancel order | Click Cancel in confirm modal | Modal closes; no order created; back to results | Order created on cancel | works
| O-08 | Duplicate orders | Order same part twice | Both orders saved; history shows 2 rows | Unique constraint error | works
| O-09 | Order API failure | Revoke Supabase key | Error message in modal; modal stays open | Unhandled exception; broken state | works
| O-10 | Orders page empty state | Visit `/orders` before any orders | "No orders placed yet." empty state | Loading spinner forever | 
| O-11 | Orders page with data | After O-01, navigate to `/orders` | Table shows part name, qty, VIN, urgency, date | Blank table |orders are not reachable
| O-12 | Order urgency preserved | Make urgent search, order a part | `urgency=urgent` saved in order record | Urgency always "standard" |works

---

## 8. Load & Performance Tests

| ID | Scenario | Target | Acceptable Threshold |
|----|----------|--------|---------------------|
| L-01 | Single search latency (Standard) | VIN + "oil filter" | First part card < 4s; all cards < 15s |works
| L-02 | Single search latency (Urgent) | Same query, Urgent mode | First part card < 2.5s; all cards < 10s |works
| L-03 | Concurrent searches | 10 simultaneous `POST /search` | All complete without 5xx; p95 < 20s | 
| L-04 | Concurrent searches (heavy) | 50 simultaneous | ≤5% 5xx; no server crash |works
| L-05 | VIN decode throughput | 20 concurrent `/vin/` requests | All respond < 3s; no 5xx |works
| L-06 | SQLite FTS under load | 20 concurrent FTS queries | `check_same_thread=False` prevents threading errors |works
| L-07 | Large catalog FTS | 10,000 parts in SQLite | FTS query returns in < 500ms |works
| L-08 | Supabase vector search | 10,000 parts, pgvector ANN | Vector search < 1s with IVFFlat index |works
| L-09 | Memory under load | 50 concurrent SSE streams | Server memory stable; no leak per stream |works
| L-10 | Frontend with 10 cards | 10 part cards rendered simultaneously | No jank; all animations complete smoothly |works

**Load test command (httpie + parallel):**
```bash
# 10 concurrent searches
for i in $(seq 1 10); do
  curl -s -N -X POST http://localhost:8000/search \
    -H "Content-Type: application/json" \
    -d '{"vin":"1XKAD49X1EJ391052","query":"oil filter","urgency":"standard"}' &
done
wait
```

---

## 9. AI Model Edge Cases

| ID | Scenario | Expected | Failure Mode |
|----|----------|----------|--------------|
| AIM-01 | Haiku vs Sonnet on identical query | Both return valid results; Haiku faster | Haiku returns empty results or all-ambiguous |works
| AIM-02 | Haiku wraps JSON in code fences | Intent/fitment parsers strip ` ```json ``` ` | `JSONDecodeError` on ` ``` ` prefix |works
| AIM-03 | Sonnet on ambiguous query | `is_ambiguous=true` for "need parts" | Named part categories not marked ambiguous |works
| AIM-04 | Haiku on ambiguous query | Same as AIM-03 | Haiku over-triggers clarify for named categories |works
| AIM-05 | LLM invents part number | Fitment returns a hallucinated part_number | Post-validation check retries or flags | Hallucinated part reaches UI |works
| AIM-06 | Fitment reasoning too long | LLM returns 2000-char reasoning | Truncated in UI with full text in detail panel | Layout broken by long string |works
| AIM-07 | Fitment confidence outside enum | LLM returns unlisted confidence string | Pydantic `ValidationError` caught; fallback confidence | Unhandled error |works

---

## 10. Security / Input Validation Tests (Set up unit testing suite)

| ID | Scenario | Expected |
|----|----------|----------|
| SEC-01 | XSS in query field | `<script>` rendered as plain text in all components; no script execution |
| SEC-02 | XSS in part name from DB | Part name with HTML tags displayed as text via React's JSX escaping |
| SEC-03 | SQL injection in query | Query passed to LLM as string; parameterized Supabase queries unaffected |
| SEC-04 | Oversized POST body | `POST /search` with 10MB body | FastAPI rejects with 413 or truncates |
| SEC-05 | CORS origin | Request from unauthorized origin | `allow_origins=["*"]` is permissive by design (single-user); documented |
| SEC-06 | VIN with SQL payload | `'; DROP TABLE vin_cache; --` as VIN | NHTSA VPIC call fails gracefully; 422 returned |
| SEC-07 | Rapid order creation | POST /orders 100x in 10s | All accepted (no rate limiting by design); no DB corruption |

---

## 11. Integration / Services Down Tests (Set up unit testing suite)

| ID | Service Down | Expected Behavior |
|----|-------------|-------------------|
| INT-01 | Supabase unavailable | API startup fails clearly; logged error |
| INT-02 | Supabase unavailable during search | SSE `error` event: "Database unavailable"; frontend shows error banner |
| INT-03 | Anthropic API down | SSE `error` event within intent step; meaningful message |
| INT-04 | Cohere API down (embed) | SSE `error` event within retrieve step |
| INT-05 | Cohere API down (rerank) | SSE `error` event or fallback RRF order used |
| INT-06 | NHTSA API down | `GET /vin/{vin}` returns 422; VIN confirmation not shown; search still submittable |
| INT-07 | SQLite FTS missing on boot | `rebuild_if_missing` recreates index from Supabase on startup |
| INT-08 | Missing env var at startup | `pydantic-settings` raises `ValidationError` with the missing field name |

---

## 12. Golden Query Regression Suite (evals)

Run via `uv run python -m ingestion.eval_runner`. All 5 must pass after any backend change.

| # | VIN | Query | Urgency | Expected |
|---|-----|-------|---------|----------|
| 1 | `1XKAD49X1EJ391052` (Kenworth T680 2014) | oil filter | standard | ✓ Correct part in top 3; High/Medium confidence |
| 2 | `3AKJGLD58FSGF7432` (Freightliner Cascadia 2015) | fuel filter | standard | ✓ Correct part in top 3 |
| 3 | `4V4NC9EH9EN157361` (Volvo VNL 2014) | need brakes | standard | ✓ `clarify` event triggered; no part cards |
| 4 | `1NPXGGGG8FD349872` (Peterbilt 386 2015) | slack adjuster | urgent | ✓ `is_ambiguous=false`; Haiku returns results |
| 5 | `1M1AW07Y2GM001234` (Mack Pinnacle 2016) | radiator | standard | ✓ Correct part in top 3 |

**Pass criteria per query:**
- `correct_part_found = True` (expected part_number in results)
- `rank_position ≤ 3`
- `clarify_triggered` matches expected column
- `latency_ms < 15000` (standard), `< 10000` (urgent)

---

## 13. UI / UX Edge Cases

| ID | Scenario | Expected |
|----|----------|----------|
| UI-01 | Very long part name (80+ chars) | Truncated with ellipsis in card; full name in detail panel header |
| UI-02 | Part with no price | Price area hidden (not "—" shown in wrong slot) |
| UI-03 | Part with no brand | Brand badge not rendered; layout intact |
| UI-04 | Part with 20+ attributes | Specifications table scrolls within detail panel; panel doesn't overflow |
| UI-05 | No vendor URLs | Sources section not rendered in detail panel |
| UI-06 | Filter sidebar on mobile (< md) | Filter sidebar hidden; results occupy full width |
| UI-07 | Navigate to `/results` directly (no state) | Redirected to `/` |
| UI-08 | Browser back button after order | `/orders` → back → `/results` with previous results | React state cleared (fresh navigation) |
| UI-09 | Urgency badge on order history | Urgent orders show orange badge; standard shows gray |
| UI-10 | OrderConfirm backdrop click | Clicking outside modal closes it (cancel) |
| UI-11 | PartDetail backdrop click | Clicking outside panel closes it |
| UI-12 | Multiple rapid card clicks | Only one detail panel open at a time |

-Failure notes : 
- Entering one character in VIN number and description activates submit button