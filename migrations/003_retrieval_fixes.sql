-- Retrieval fixes. Run in Supabase SQL editor after 002_vendor_outreach.sql.
--
-- 001 created an ivfflat index with lists = 100 on a ~170-row table (guidance is
-- lists ≈ rows/1000) and created it BEFORE any data existed, so the centroids were
-- never trained — queries scanned ~1-2 near-random vectors. HNSW needs no training
-- step, works on empty tables, and is the better choice at this corpus size.

DROP INDEX IF EXISTS parts_embedding_idx;

CREATE INDEX IF NOT EXISTS parts_embedding_hnsw_idx
    ON parts USING hnsw (embedding vector_cosine_ops);
