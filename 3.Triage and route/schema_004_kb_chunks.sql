-- RAG Q&A ("Ask Sahyog") knowledge-base chunks.
-- Requires pgvector (already enabled by schema.sql). Additive-only, run
-- after the base schema. Populated by `python -m app.rag_ingest`, which
-- re-embeds knowledge_base/*.md and replaces rows per `source` on every run.

CREATE TABLE IF NOT EXISTS kb_chunks (
    id          BIGSERIAL PRIMARY KEY,
    source      TEXT NOT NULL,       -- knowledge_base/*.md filename this chunk came from
    title       TEXT NOT NULL,       -- heading the chunk falls under
    chunk_text  TEXT NOT NULL,
    embedding   vector(384) NOT NULL, -- all-MiniLM-L6-v2 dim, same model as active_tickets.embedding
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_kb_chunks_source ON kb_chunks(source);

-- ANN index for the retrieval pass (cosine distance), same operator class
-- active_tickets.embedding already uses.
CREATE INDEX IF NOT EXISTS idx_kb_chunks_embedding
    ON kb_chunks USING hnsw (embedding vector_cosine_ops);
