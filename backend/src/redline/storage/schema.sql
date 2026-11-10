CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY,
    title TEXT NOT NULL,
    current_version INTEGER NOT NULL CHECK (current_version >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document_versions (
    document_id UUID NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    version INTEGER NOT NULL CHECK (version >= 1),
    text TEXT NOT NULL,
    author TEXT NOT NULL,
    summary TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (document_id, version)
);

CREATE INDEX IF NOT EXISTS documents_updated_at_index ON documents (updated_at DESC);
