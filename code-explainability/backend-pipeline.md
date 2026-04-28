# Backend — Pipeline

## backend/app/vin/decoder.py

**What it does:** Decodes a VIN into a `VINSpec` by first checking the `vin_cache` table in Supabase, then falling back to the NHTSA VPIC API. On a successful NHTSA response it upserts the decoded record to `vin_cache` for future cache hits. Returns `None` on network failure so the caller can return a 422.

**External services:** Supabase (`vin_cache` table), NHTSA VPIC REST API (`{nhtsa_api_base}/decodevinvalues/{vin}`).

**What calls it:** `api/vin.py` (GET /vin/{vin}), `api/search.py` (first step in the search pipeline), `api/procurement.py` (VIN decode on job creation).

---

## backend/app/pipeline/intent.py

**What it does:** Calls the Anthropic API with a structured system prompt to parse a technician's free-text query into `IntentResult` — a canonical part category, key-value attributes, and an ambiguity flag. If `is_ambiguous=True`, a `clarifying_question` is returned so the API can short-circuit the pipeline and ask the user to clarify.

**External services:** Anthropic API (`claude-sonnet-4-6` standard / `claude-haiku-4-5-20251001` urgent, temperature=0).

**What calls it:** `api/search.py` (step 2 of the pipeline, after VIN decode).

---

## backend/app/pipeline/embed.py

**What it does:** Embeds a single query string into a 1024-dimension float vector using Cohere's `embed-english-v3.0` model with `input_type="search_query"`. This vector is used for the pgvector ANN leg of hybrid retrieval.

**External services:** Cohere Embed API.

**What calls it:** `api/search.py` (step 3 of the pipeline, before `retrieve`).

---

## backend/app/pipeline/retrieve.py

**What it does:** Runs pgvector ANN (via Supabase `match_parts` RPC) and SQLite BM25 (via `FTSIndex.query`) concurrently with `asyncio.gather`, then merges the two ranked lists using Reciprocal Rank Fusion (k=60). Returns the top-N part IDs sorted by combined RRF score.

**External services:** Supabase pgvector RPC (`match_parts`), SQLite FTS (local file).

**What calls it:** `api/search.py` (step 4 of the pipeline).

---

## backend/app/pipeline/rerank.py

**What it does:** Takes the candidate `Part` list from retrieval and re-orders it using Cohere's `rerank-english-v3.0` model against the original query string. Returns parts in the order Cohere considers most relevant.

**External services:** Cohere Rerank API.

**What calls it:** `api/search.py` (step 5 of the pipeline, after parts are fetched from Supabase).

---

## backend/app/pipeline/fitment.py

**What it does:** Assigns a `FitmentResult` to each part. First tries a structured match against `part.fit_notes` (make/model/engine/year_range) — an exact match returns `HIGH` confidence immediately. If fit_notes are absent or don't fully match, falls back to the Anthropic API for an LLM-based confidence assessment.

**External services:** Anthropic API (`claude-sonnet-4-6` / `claude-haiku-4-5-20251001`, temperature=0) for LLM fallback only.

**What calls it:** `api/search.py` (step 6, called once per part in the stream loop).

---

## backend/app/pipeline/stream.py

**What it does:** Pure helper that serialises pipeline outputs into SSE-formatted strings. Four event types: `part` (part + fitment payload), `clarify` (question for the user), `done` (stream end), `error` (pipeline failure message).

**External services:** None.

**What calls it:** `api/search.py` yields the output of these functions directly into the `StreamingResponse`.
