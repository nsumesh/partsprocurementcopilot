# Backend — Workers

## backend/app/workers/job_processor.py

**What it does:** Background async coroutine started at FastAPI lifespan. Polls every 30 seconds. In each cycle: (1) fetches jobs in `outreach_sent` or `follow_up_sent` whose `respond_at <= now()`, simulates the vendor response via `response_simulator`, parses it via `email_parser`, generates a follow-up email if fields are missing (→ `follow_up_required`) or marks the job `confirmed` if all fields present, writes a `procurement_events` row for each transition. (2) Fetches `confirmed` jobs with null `ranking_score`, computes the composite score via `ranker`, transitions to `ranked`. Creates its own `AsyncAnthropic` client from settings — does not depend on `app.state.anthropic`. Per-job `try/except` keeps one failed job from blocking the rest; errors are logged and written to `procurement_events` metadata.

**External services:** Supabase (`procurement_jobs`, `procurement_events`), Anthropic API (via agent modules).

**What calls it:** `app/main.py` lifespan — started as `asyncio.create_task(job_processor_loop(app.state))` and cancelled on shutdown.
