-- Run in Supabase SQL editor

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Canonical parts table (OE + aftermarket)
CREATE TABLE IF NOT EXISTS parts (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    part_number   TEXT NOT NULL,
    name          TEXT NOT NULL,
    description   TEXT,
    category      TEXT NOT NULL,
    source        TEXT NOT NULL CHECK (source IN ('OE', 'aftermarket')),
    brand         TEXT,
    price_usd     NUMERIC(10, 2),
    fit_notes     JSONB NOT NULL DEFAULT '{}',
    attributes    JSONB NOT NULL DEFAULT '{}',
    vendor_urls   JSONB NOT NULL DEFAULT '[]',
    embedding     vector(1024),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (part_number, source)
);

CREATE INDEX IF NOT EXISTS parts_embedding_idx
    ON parts USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- pgvector search function called by the API
CREATE OR REPLACE FUNCTION match_parts(
    query_embedding vector(1024),
    match_count     int
)
RETURNS TABLE (
    id          UUID,
    part_number TEXT,
    distance    float
)
LANGUAGE sql STABLE
AS $$
    SELECT id, part_number, embedding <=> query_embedding AS distance
    FROM parts
    ORDER BY distance
    LIMIT match_count;
$$;

-- Intent records (no payment, no external integration)
CREATE TABLE IF NOT EXISTS orders (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    part_id     UUID REFERENCES parts(id) ON DELETE SET NULL,
    part_number TEXT NOT NULL,
    part_name   TEXT NOT NULL,
    quantity    INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    vin         TEXT,
    query       TEXT,
    urgency     TEXT NOT NULL DEFAULT 'standard' CHECK (urgency IN ('standard', 'urgent')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Decoded VIN cache (NHTSA VPIC results + 5 eval VIN seeds)
CREATE TABLE IF NOT EXISTS vin_cache (
    vin        TEXT PRIMARY KEY,
    make       TEXT,
    model      TEXT,
    year       INTEGER,
    engine     TEXT,
    gvwr       TEXT,
    raw_vpic   JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- RLS: permissive for single-user tool (no auth)
ALTER TABLE parts     ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders    ENABLE ROW LEVEL SECURITY;
ALTER TABLE vin_cache ENABLE ROW LEVEL SECURITY;

CREATE POLICY allow_all_parts     ON parts     FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY allow_all_orders    ON orders    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY allow_all_vin_cache ON vin_cache FOR ALL USING (true) WITH CHECK (true);
