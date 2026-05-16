-- V1__create_function_registry.sql
-- Stores metadata for every uploaded and verified Python function.
-- The 'url_hash' is the token embedded in the public invocation URL.

CREATE TABLE IF NOT EXISTS function_registry (
    id              BIGSERIAL       PRIMARY KEY,

    -- SHA-256 hex digest used as the public URL token.
    -- 64 characters, indexed for fast look-up on every invocation request.
    url_hash        CHAR(64)        NOT NULL UNIQUE,

    -- Absolute path to the directory on disk that contains handler.py
    -- (and optionally requirements.txt).
    storage_path    TEXT            NOT NULL,

    -- Original filename supplied by the uploader (informational only).
    original_filename TEXT          NOT NULL,

    -- Status transitions:  PENDING_VERIFICATION → VERIFIED | REJECTED
    status          VARCHAR(32)     NOT NULL DEFAULT 'PENDING_VERIFICATION',

    -- Timestamp recorded by the database (UTC) when the row is inserted.
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- Timestamp of the last status update (nullable until first change).
    updated_at      TIMESTAMPTZ
);

-- Index used when the Firecracker orchestrator resolves a hash → path.
CREATE INDEX idx_function_registry_url_hash ON function_registry (url_hash);

-- Index useful for administrative queries and audit reports.
CREATE INDEX idx_function_registry_status   ON function_registry (status);
CREATE INDEX idx_function_registry_created  ON function_registry (created_at DESC);
