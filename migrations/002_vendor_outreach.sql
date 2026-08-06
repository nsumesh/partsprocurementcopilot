-- Vendor outreach schema (v2.0) — reconstructed so the repo is reproducible from source.
-- Idempotent: safe to run on a fresh project AND on the live DB where these tables
-- were originally created out-of-band via the Supabase SQL editor.
-- Run in Supabase SQL editor after 001_initial.sql.

-- Simulated vendor directory
CREATE TABLE IF NOT EXISTS vendors (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name           TEXT NOT NULL UNIQUE,          -- upsert key (vendor_seeder on_conflict="name")
    email          TEXT NOT NULL,
    region         TEXT,
    type           TEXT NOT NULL,
    brands_carried JSONB NOT NULL DEFAULT '[]',
    response_rate  NUMERIC(3, 2) NOT NULL DEFAULT 0.75,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Which vendor carries which part, at what price/lead time
CREATE TABLE IF NOT EXISTS vendor_parts (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id         UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    part_id           UUID NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
    list_price        NUMERIC(10, 2),
    delivery_estimate TEXT,
    delivery_hours    INTEGER,
    in_stock          BOOLEAN NOT NULL DEFAULT true,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (vendor_id, part_id)                   -- upsert key (vendor_seeder on_conflict)
);

-- One outreach job per (part, vendor); mutable current state
CREATE TABLE IF NOT EXISTS procurement_jobs (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    part_id                   UUID REFERENCES parts(id) ON DELETE SET NULL,
    vendor_id                 UUID REFERENCES vendors(id) ON DELETE SET NULL,
    part_number               TEXT NOT NULL,
    part_name                 TEXT NOT NULL,
    vin                       TEXT NOT NULL,
    query                     TEXT NOT NULL,
    urgency                   TEXT NOT NULL DEFAULT 'standard'
                              CHECK (urgency IN ('standard', 'urgent')),
    urgency_deadline          TIMESTAMPTZ,
    status                    TEXT NOT NULL DEFAULT 'created',
    outreach_email            TEXT,
    response_email            TEXT,
    follow_up_email           TEXT,
    parsed_availability       TEXT,
    parsed_unit_price         NUMERIC(10, 2),
    parsed_quantity_available INTEGER,
    parsed_delivery_date      TEXT,
    parsed_delivery_hours     INTEGER,
    ranking_score             DOUBLE PRECISION,
    respond_at                TIMESTAMPTZ,
    attempt_count             INTEGER NOT NULL DEFAULT 0,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ
);

-- Column + constraint upgrades for pre-existing deployments
ALTER TABLE procurement_jobs ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE procurement_jobs DROP CONSTRAINT IF EXISTS procurement_jobs_status_check;
ALTER TABLE procurement_jobs ADD CONSTRAINT procurement_jobs_status_check
    CHECK (status IN (
        'created', 'outreach_sent', 'response_received', 'parsed',
        'follow_up_required', 'follow_up_sent', 'confirmed', 'ranked',
        'accepted', 'rejected', 'failed'
    ));

-- Append-only transition log with actor attribution (user vs worker)
CREATE TABLE IF NOT EXISTS procurement_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id      UUID NOT NULL REFERENCES procurement_jobs(id) ON DELETE CASCADE,
    from_status TEXT,
    to_status   TEXT NOT NULL,
    actor       TEXT NOT NULL,
    metadata    JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for the worker's 30s poll predicates and the board queries
CREATE INDEX IF NOT EXISTS procurement_jobs_status_respond_at_idx
    ON procurement_jobs (status, respond_at);
CREATE INDEX IF NOT EXISTS procurement_jobs_status_ranking_score_idx
    ON procurement_jobs (status, ranking_score);
CREATE INDEX IF NOT EXISTS procurement_jobs_created_at_idx
    ON procurement_jobs (created_at DESC);
CREATE INDEX IF NOT EXISTS procurement_events_job_id_created_at_idx
    ON procurement_events (job_id, created_at);
CREATE INDEX IF NOT EXISTS vendor_parts_part_id_in_stock_idx
    ON vendor_parts (part_id, in_stock);

-- RLS: the browser holds the anon key (Realtime subscription on procurement_jobs).
-- Anon gets SELECT only — no write policies, so the state machine can't be bypassed
-- client-side. The backend uses the service-role key, which bypasses RLS.
ALTER TABLE vendors            ENABLE ROW LEVEL SECURITY;
ALTER TABLE vendor_parts       ENABLE ROW LEVEL SECURITY;
ALTER TABLE procurement_jobs   ENABLE ROW LEVEL SECURITY;
ALTER TABLE procurement_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS allow_all_vendors            ON vendors;
DROP POLICY IF EXISTS allow_all_vendor_parts       ON vendor_parts;
DROP POLICY IF EXISTS allow_all_procurement_jobs   ON procurement_jobs;
DROP POLICY IF EXISTS allow_all_procurement_events ON procurement_events;

DROP POLICY IF EXISTS read_vendors            ON vendors;
DROP POLICY IF EXISTS read_vendor_parts       ON vendor_parts;
DROP POLICY IF EXISTS read_procurement_jobs   ON procurement_jobs;
DROP POLICY IF EXISTS read_procurement_events ON procurement_events;

CREATE POLICY read_vendors            ON vendors            FOR SELECT USING (true);
CREATE POLICY read_vendor_parts       ON vendor_parts       FOR SELECT USING (true);
CREATE POLICY read_procurement_jobs   ON procurement_jobs   FOR SELECT USING (true);
CREATE POLICY read_procurement_events ON procurement_events FOR SELECT USING (true);

-- Realtime: the board subscribes to procurement_jobs changes
DO $$
BEGIN
    ALTER PUBLICATION supabase_realtime ADD TABLE procurement_jobs;
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;
