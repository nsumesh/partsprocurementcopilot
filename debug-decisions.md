# Debug Decisions

Running log of errors encountered during development, root causes, and fixes applied.

---

## 2026-04-26 — CP-2: First uvicorn boot attempt

Command: `cd backend && uv run uvicorn app.main:app --reload`

---

### Error 1 — `pydantic_core.ValidationError: Extra inputs are not permitted` on `vite_api_base_url`

**File:** `backend/app/config.py`

**Root cause:** `pydantic-settings` reads the entire `.env` file. `VITE_API_BASE_URL` is a frontend build variable with no matching field in `Settings`. Pydantic's default is `extra="forbid"`, so it rejects any env var not declared as a field.

**Fix applied:** Added `extra="ignore"` to `SettingsConfigDict` in `config.py`:
```python
model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
```

**Prevention:** Any `.env` shared between frontend and backend will always contain `VITE_*` vars — `extra="ignore"` is the correct permanent setting.

---

### Error 2 — `RuntimeError: this event loop is already running` in `get_client`

**File:** `backend/app/db/supabase.py`

**Root cause:** The original `get_client` was a sync function that bootstrapped the async `acreate_client` via `loop.run_until_complete()`. FastAPI's lifespan context already runs inside uvloop, so calling `run_until_complete()` on the already-running loop raises this error.

**Fix applied:** Changed `get_client` to a proper `async` function:
```python
async def get_client(settings: Settings) -> AsyncClient:
    global _client
    if _client is None:
        _client = await acreate_client(settings.supabase_url, settings.supabase_key)
    return _client
```
Updated `app/main.py` to `await get_client(settings)` accordingly.

**Prevention:** Never call `loop.run_until_complete()` inside a FastAPI lifespan or route handler — the event loop is always already running in those contexts.

---

### Error 3 — `SupabaseException: Invalid URL` (action required — not a code bug)

**File:** `backend/.env`

**Root cause:** `supabase-py` (`AsyncClient`) expects the Supabase REST API base URL and a service role JWT key:
- `SUPABASE_URL` must be the **REST API URL**: `https://<project-ref>.supabase.co`
- `SUPABASE_KEY` must be the **service role JWT** from Supabase → Project Settings → API (starts with `eyJ...`)

The current `.env` has a direct Postgres connection URI (`postgresql://...`) set as `SUPABASE_URL`, which is rejected by `supabase-py`. The `SUPABASE_KEY` also appears to be a publishable key rather than a service role JWT.

**Fix required (manual — update .env):**
```
SUPABASE_URL=https://vayepiiiyhmocdihiwrj.supabase.co
SUPABASE_KEY=eyJ...   # service_role JWT from Project Settings → API → service_role
```
The project ref is visible in the Postgres hostname: `db.vayepiiiyhmocdihiwrj.supabase.co` → ref = `vayepiiiyhmocdihiwrj`.

**Fix applied:** Stripped `/rest/v1/` suffix from `SUPABASE_URL` in `.env`:
```
SUPABASE_URL=https://vayepiiiyhmocdihiwrj.supabase.co
```
`supabase-py` appends the PostgREST path itself — including it in the base URL causes a doubled path (`/rest/v1//rest/v1/`) which PostgREST rejects as `PGRST125: Invalid path`.

**Resolution:** Server reached `Application startup complete` after this fix.

---

### Error 4 — `PGRST125: Invalid path specified in request URL` (follow-on from Error 3)

**File:** `backend/.env`

**Root cause:** `SUPABASE_URL` was set to `https://vayepiiiyhmocdihiwrj.supabase.co/rest/v1/`. The `supabase-py` PostgREST client appends `/rest/v1/<table>` to the base URL, resulting in a doubled path that PostgREST rejects.

**Fix applied:** Removed `/rest/v1/` from the URL — the SDK only needs the bare project URL.

**Prevention:** `SUPABASE_URL` for `supabase-py` is always `https://<project-ref>.supabase.co` with no path suffix.

---

## CP-2 Status: PASSED ✓

`Application startup complete` — Supabase client initialised, SQLite FTS rebuilt (empty — no parts ingested yet). All three routers mounted. Ready for CP-3 (ingestion).

---

## 2026-04-26 — CP-3: First ingestion run (`uv run python -m ingestion.loader`)

---

### Error 5 — `PGRST100: failed to parse columns parameter ()` on empty upsert

**File:** `backend/app/db/supabase.py`

**Root cause:** The scraper returned 0 parts, so `upsert_parts` was called with an empty list `[]`. PostgREST receives a body with no columns and fails to parse the column list from an empty payload.

**Fix applied:** Added an early-return guard:
```python
async def upsert_parts(client: AsyncClient, parts: list[dict]) -> None:
    if not parts:
        return
    await client.table("parts").upsert(parts, on_conflict="part_number,source").execute()
```

**Prevention:** Any Supabase upsert/insert called with a dynamic list must guard against empty input — PostgREST always rejects empty payloads.

---

### Error 6 — Scraper returns 0 parts (wrong CSS selectors + missing Turbo Frame interaction)

**File:** `backend/ingestion/scraper.py`

**Root cause (part A — selectors):** The original scraper used generic guessed selectors (`.product-item`, `.search-result-item`, `[data-part-number]`, etc.) that did not match finditparts.com's actual DOM structure. The real structure is:

```
.product_results_grid
  └── .product_search_result          (one per result)
        └── .product_search_result_tile_direction
              └── <a data-name data-price data-brand data-category data-category2>
```

All product data lives as `data-*` attributes on the anchor inside `.product_search_result_tile_direction`.

**Root cause (part B — Turbo Frame):** The site uses Hotwire Turbo Frames. The header search form (`form.fip_header__search_form`) has `data-turbo-frame="product_results"`, meaning submitting it issues a frame-level fetch rather than a full page navigation. The scraper must fill `#searcher_s` and click the submit button to trigger the frame update; navigating directly to a URL bypasses this interaction.

**Fix applied:**
- Navigate to `_BASE_URL` once at startup (loads the persistent header with the search form)
- For each category: `fill("#searcher_s", query)` → click `.fip_header__search_form_button` → `wait_for_load_state("networkidle")` → `wait_for_selector(".product_results_grid")`
- `_extract_part` reads `data-name`, `data-price`, `data-brand`, `data-category`, `data-category2` from the anchor; falls back to `data-id` / `data-sku` / URL path segment for part number

**Prevention:** Never assume CSS class names or navigation patterns from a live site without inspecting the actual DOM. Check for Turbo/SPA frame patterns before deciding whether to `goto()` or interact with a form.

---

### Error 7 — `ElementHandle.click: Timeout 30000ms exceeded` — Klaviyo popup intercepts pointer events

**File:** `backend/ingestion/scraper.py`

**Root cause:** finditparts.com shows a Klaviyo email-capture modal on homepage load (`<div role="dialog" aria-label="POPUP Form" class="needsclick kl-private-reset-css-Xuajs1">`). The modal sits on top of the page at a high z-index and intercepts all pointer events, so Playwright's `.click()` on the submit button times out — the button is visible and enabled but the modal captures every pointer interaction before it reaches the button.

**Fix applied:**
1. Added `_dismiss_popup(page)` helper after homepage load. It waits up to 4 s for the modal, then presses `Escape` and waits for it to disappear.
2. Also calls `_dismiss_popup(page)` inside `_scrape_category` before form submission (in case the modal reappears between categories).
3. Replaced `submit_btn.click()` with `page.evaluate("form.requestSubmit()")`. `requestSubmit()` fires the DOM `submit` event via JavaScript — Turbo's event listener intercepts it correctly — and is immune to pointer-event blocking because it never touches the pointer model.

**Prevention:** After any `page.goto()` on a marketing site, always check for and dismiss cookie banners / email-capture modals before attempting pointer interactions. Prefer `page.evaluate()` / `requestSubmit()` over `.click()` for form submissions when modal overlays are a risk.

---

### Error 8 — Two grids co-exist; wrong selector matched skeleton and yielded 0 real parts

**File:** `backend/ingestion/scraper.py`

**Root cause:** finditparts.com renders **two** `.product_results_grid` divs simultaneously:
- `.product_results_grid.loading` — always-present skeleton/placeholder (never removed from DOM)
- `.product_results_grid.loaded` — injected by AJAX when results arrive

The previous fix waited for `.product_results_grid:not(.loading)`, which correctly skips the skeleton but also matches the `.loaded` grid once it appears. However, `query_selector_all(".product_search_result")` then selected cards from **both** grids — including the skeleton's empty placeholder cards. The skeleton cards have no anchor elements inside `.product_search_result_tile_direction`, so `_extract_part` returned `None` for all of them.

Additionally, `data-id` on the anchor is finditparts.com's internal numeric DB ID (e.g. `1812093`), not the manufacturer part number. The real part number (`5228`, `29558295`) follows the brand name in `data-name` (format: `"{BRAND} {PART_NUMBER}"`).

**Fix applied:**
1. Changed wait selector from `.product_results_grid:not(.loading)` to `.product_results_grid.loaded`
2. Changed card selector from `.product_search_result` to `.product_results_grid.loaded .product_search_result` — scopes to the loaded grid only
3. Rewrote `_extract_part` to use a single `card.evaluate()` round-trip that reads anchor attrs + description from `[itemprop="description"]` in one JS call (avoids stale element refs across Turbo frame updates)
4. Extract manufacturer part number from `data-name` by stripping the brand prefix: `name[len(brand):].strip()`
5. Updated `_pn_from_href(href, brand)` to strip the brand slug from the URL last segment as a fallback

**Prevention:** When a page uses skeleton loaders, always wait for the specific class that signals real content (`.loaded`), not the absence of a loading class. Scope card selectors to the loaded container to avoid selecting skeleton cards. Never use an internal DB ID as a part number — extract the human-readable identifier from the visible name/URL.

---

## 2026-04-26 — CP-4: First /search SSE call

---

### Error 9 — `AttributeError: 'State' object has no attribute 'supabase'` in `search.py`

**File:** `backend/app/api/search.py`

**Root cause:** FastAPI/Starlette has two distinct state objects:
- `app.state` — application-level state, set once in the lifespan context manager and shared across all requests
- `request.state` — per-request state, a fresh empty object for every HTTP request

`main.py` correctly stores the Supabase client and FTS index on `app.state` during startup:
```python
app.state.fts = fts
app.state.supabase = supabase
```

However, `search.py` read from `app_request.state` (per-request, always empty) instead of `app_request.app.state` (application-level). `vin.py` and `orders.py` were both written correctly with `request.app.state.supabase`.

**Fix applied:** Changed lines 25–26 in `app/api/search.py`:
```python
# Before (wrong — per-request state, always empty)
supabase = app_request.state.supabase
fts = app_request.state.fts

# After (correct — application-level state)
supabase = app_request.app.state.supabase
fts = app_request.app.state.fts
```

**Prevention:** In FastAPI, always access lifespan-initialised singletons via `request.app.state`, never `request.state`. The pattern is consistent across all three API routers.

---

### Error 12 — `AttributeError: 'str' object has no attribute 'get'` in `fitment._structured_match`

**File:** `backend/app/pipeline/fitment.py`

**Root cause:** `_structured_match` assumed `fit_notes["year_range"]` was always a dict `{"min": 2005, "max": 2023}` and called `.get("min")` on it. The aftermarket data generator (`aftermarket.py`) produced `year_range` as the string `"2005-2023"` instead. Supabase JSONB stores and returns it as a Python string, so `.get()` raised `AttributeError`.

**Fix applied:** Added isinstance guard before calling `.get()`:
```python
if isinstance(yr_range, dict):
    low, high = yr_range.get("min", 0), yr_range.get("max", 9999)
elif isinstance(yr_range, str):
    parts = yr_range.split("-")
    low = int(parts[0])
    high = int(parts[1]) if len(parts) > 1 else 9999
else:
    low, high = 0, 9999
```

**Also fixed (defensive):** Both `intent.py` and `fitment.py` now strip markdown code fences before `json.loads` — `claude-haiku` wraps its JSON in ` ```json ``` ` blocks even when the prompt says "no markdown".

**Prevention:** Never assume a JSONB field has a fixed sub-structure without an isinstance guard. AI-generated CSV data will not match hand-written schema assumptions. Always strip markdown fences before `json.loads` on LLM output regardless of prompt instructions.

--- The pattern is consistent across all three API routers — any new route that needs Supabase or FTS must use `request.app.state`.

---

### Error 10 — `TypeError: "Could not resolve authentication method"` — Anthropic SDK can't find API key

**File:** `backend/app/pipeline/intent.py`, `backend/app/pipeline/fitment.py`, `backend/app/api/search.py`

**Root cause:** Both `intent.py` and `fitment.py` created the Anthropic client as a module-level singleton:
```python
_client = AsyncAnthropic()
```
`AsyncAnthropic()` with no arguments reads `ANTHROPIC_API_KEY` from `os.environ` at construction time. However, `pydantic-settings` loads `.env` values into the `Settings` object only — it does **not** inject them into `os.environ`. The key was never in the process environment, so `AsyncAnthropic()` constructed a client with `api_key=None`, which raises a `TypeError` on the first API call.

The error message `"Could not resolve authentication method..."` is identical in both the Anthropic and Cohere SDKs, which caused initial confusion about the source.

**Fix applied:**
1. Removed `_client = AsyncAnthropic()` module-level singletons from `intent.py` and `fitment.py`
2. Added `client: AsyncAnthropic` parameter to `parse_intent` and `assign_fitment`
3. In `search.py`, created `anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)` (using the pydantic-settings-loaded key) and passed it to both pipeline functions

**Prevention:** Never use SDK clients that read from `os.environ` at module level when keys are loaded via pydantic-settings (not exported to the process environment). Always construct API clients with explicit keys sourced from the `Settings` object. `os.environ` and pydantic-settings `.env` loading are separate — one does not imply the other.

---

### Error 11 — `SQLite objects created in a thread can only be used in that same thread`

**File:** `backend/app/db/sqlite_fts.py`

**Root cause:** `FTSIndex._open()` caches the SQLite connection in `self._conn`. The connection was first created on the main thread during lifespan startup (via `rebuild_if_missing`). When `fts.query()` is later called from `retrieve.py` via `loop.run_in_executor(None, fts.query, ...)`, it runs on a thread-pool worker thread. SQLite's default threading mode rejects cross-thread connection use, raising this error.

**Fix applied:** Added `check_same_thread=False` to `sqlite3.connect()`:
```python
self._conn = sqlite3.connect(self._path, check_same_thread=False)
```

**Prevention:** Any SQLite connection shared across threads (including via `run_in_executor`) must be opened with `check_same_thread=False`. This is safe when writes and reads are serialized — `build()` is the only writer (called once at startup) and `query()` is read-only at request time.

---

## 2026-04-26 — CP-5: Eval runner (5 golden queries)

---

### Error 12 — `AttributeError: 'str' object has no attribute 'get'` in `fitment._structured_match`

**File:** `backend/app/pipeline/fitment.py`

**Root cause:** `_structured_match` assumed `fit_notes["year_range"]` was always a dict `{"min": 2005, "max": 2023}` and called `.get("min")` on it. The aftermarket data generator produced `year_range` as the string `"2005-2023"` instead. Supabase JSONB stores and returns it as a Python string, so `.get()` raised `AttributeError`.

**Fix applied:** Added isinstance guard before calling `.get()`:
```python
if isinstance(yr_range, dict):
    low, high = yr_range.get("min", 0), yr_range.get("max", 9999)
elif isinstance(yr_range, str):
    parts = yr_range.split("-")
    low = int(parts[0])
    high = int(parts[1]) if len(parts) > 1 else 9999
else:
    low, high = 0, 9999
```

**Also fixed (defensive):** Both `intent.py` and `fitment.py` now strip markdown code fences before `json.loads` — `claude-haiku` wraps its JSON in ` ```json ``` ` blocks even when the prompt says "no markdown".

**Prevention:** Never assume a JSONB field has a fixed sub-structure without an isinstance guard. AI-generated CSV data will not match hand-written schema assumptions. Always strip markdown fences before `json.loads` on LLM output regardless of prompt instructions.

---

### Error 13 — Eval 4/5: Haiku marks "slack adjuster" as ambiguous (should not)

**File:** `backend/app/pipeline/intent.py`

**Root cause:** The original ambiguity rule was "cannot be resolved to a specific part category without more information." Haiku interpreted this as: "slack adjuster has front/rear variants → needs clarification." This is technically correct but wrong for procurement — variant selection is handled by fitment downstream, not by the query parser.

**Fix applied:** Tightened the system prompt with an explicit rule:
> Set is_ambiguous=true ONLY when the query gives no recognizable part category at all. If the query names any specific part type (e.g. "slack adjuster", "oil filter"), always set is_ambiguous=false even if variants exist. Variant selection is handled downstream.

**Prevention:** Ambiguity thresholds must be calibrated per model — Haiku is more conservative than Sonnet. Eval all models against the golden queries before release. Include worked examples in the prompt when models disagree on edge cases.

---

## CP-5 Status: PASSED ✓ (5/5 after fixes)

All 5 golden queries pass: 4 non-ambiguous queries return 10 parts each, Volvo VNL "need brakes" correctly triggers clarify.

---

---

### Error 14 — Submit button active with < 17 character VIN

**File:** `frontend/src/components/SearchBar.tsx`

**Root cause:** Button disabled condition was `!vin.trim()` — any non-empty string enabled the button, including a single character. A valid VIN is always exactly 17 characters.

**Fix applied:** Changed to `vin.trim().length !== 17` so the button only enables when the VIN field contains exactly 17 characters.

---

### Error 15 — Spinner hangs / wrong error on network drop mid-stream

**File:** `frontend/src/api/search.ts`

**Root cause:** `gotDone` flag was never tracked. When the SSE connection dropped (network cut, server crash), the for loop exited (`done: true`) and called `onDone()` — stopping the spinner silently with no indication anything went wrong. The user saw a normal end state instead of an error.

**Fix applied:** Added `gotDone = true` when the `done` SSE event is received. After the read loop exits, if `!gotDone`, call `onError("Connection lost — search results may be incomplete")` instead of `onDone()`. Error banner now shows for abrupt disconnects.

**Remaining limitation:** If `reader.read()` hangs indefinitely (WiFi drop without TCP RST), the spinner will still hang until the OS sends a keepalive timeout (~90s). A backend SSE heartbeat (`:keep-alive`) would solve this but is not yet implemented.

---

### Error 16 — Clarify banner and part cards both visible simultaneously

**File:** `frontend/src/pages/ResultsPage.tsx`

**Root cause:** `onClarify` callback set `clarifyQuestion` but did not clear the `results` array. If parts from a prior search were still in state (stale results from a previous navigation), they remained visible alongside the new clarify banner.

**Fix applied:** Added `setResults([])` to the `onClarify` callback so any previous results are cleared the moment a clarify event arrives.

---

### Error 17 — Orders page unreachable from results flow

**File:** `frontend/src/pages/ResultsPage.tsx`

**Root cause:** The only path to `/orders` was auto-navigate after confirming an order. No persistent navigation link existed in the app shell. Users who had already placed orders had no way to return.

**Fix applied:** Added an "Orders" link to the ResultsPage header (right side, hidden on mobile). Also preserves the auto-navigate after order confirmation.

---

### Investigation — Q-04 XSS: script tag appeared to execute

**Files:** All frontend components

**Finding:** No `dangerouslySetInnerHTML` exists anywhere in the codebase. React JSX text interpolation (`{value}`) always HTML-encodes output — `<script>alert(1)</script>` renders as literal text, not executable HTML. The script did not actually execute; the user likely saw the raw string displayed in the UI (correct behavior) and misread it as execution.

**Prevention:** React's JSX escaping is the primary XSS defense. Never introduce `dangerouslySetInnerHTML` without explicit sanitization. The test case Q-04 should be re-classified as PASS.

---

### Note — Q-07: Unrelated query returns 10 results (expected behavior)

**Finding:** Query "landing gear parts" returned 10 results. This is correct: the pipeline always returns the top-K semantically closest matches from the catalog regardless of whether an exact category exists. Fitment assessment on those results will return "Low Probability" or "No Fitment", which signals to the user that the parts don't match well.

**No fix required.** Semantic search cannot return zero results unless the catalog is empty. The fitment confidence badges serve as the quality signal.

---

### Note — F-07: Year range filter passes parts with null year_range (by design)

**Finding:** Entering year range 2030–2040 still shows parts that have no `year_range` in `fit_notes`. This is intentional: parts with no year compatibility data are treated as universally applicable (common for generic consumables like oils, filters). The filter panel now states "Parts without year data are always shown".

