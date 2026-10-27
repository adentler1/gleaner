-- Initial schema: the full data model from SPEC.md, fixed as of milestone 1.
-- Tables beyond runs/items/item_versions are unused by milestone 1a's own
-- code but are created now so later milestones never need a schema
-- migration just to catch up with a design that was already decided.

CREATE TABLE runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('ok', 'failed', 'blocked')),
    http_code INTEGER,
    records_found INTEGER,
    records_with_missing_required INTEGER,
    error TEXT,
    snapshot_path TEXT
);
CREATE INDEX idx_runs_source_started ON runs (source_id, started_at);

CREATE TABLE items (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    watch_id TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    title TEXT,
    deadline TEXT,
    deadline_raw TEXT,
    published_at TEXT,
    published_at_raw TEXT,
    first_seen_at TEXT NOT NULL,
    last_checked_at TEXT NOT NULL,
    last_changed_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    extraction_version INTEGER NOT NULL DEFAULT 1,
    cluster_key TEXT,
    raw_fields TEXT NOT NULL,          -- JSON: every declared field as last extracted
    unparsed_fields TEXT,              -- JSON list: declared fields that were empty/unparsed
    first_seen_run_id INTEGER REFERENCES runs (id)
);
CREATE INDEX idx_items_source ON items (source_id);
CREATE INDEX idx_items_watch ON items (watch_id);
CREATE INDEX idx_items_cluster_key ON items (cluster_key);

CREATE TABLE item_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT NOT NULL REFERENCES items (id),
    run_id INTEGER NOT NULL REFERENCES runs (id),
    changed_fields TEXT NOT NULL,      -- JSON list of field names
    old_values TEXT NOT NULL,          -- JSON object
    new_values TEXT NOT NULL,          -- JSON object
    realert BOOLEAN NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_item_versions_item ON item_versions (item_id);

CREATE TABLE scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT NOT NULL REFERENCES items (id),
    score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
    reason TEXT,
    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_scores_item ON scores (item_id);

CREATE TABLE feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT NOT NULL REFERENCES items (id),
    label TEXT NOT NULL CHECK (label IN ('relevant', 'not_relevant')),
    channel TEXT NOT NULL CHECK (channel IN ('telegram', 'app')),
    created_at TEXT NOT NULL
);
CREATE INDEX idx_feedback_item ON feedback (item_id);

CREATE TABLE deadlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT NOT NULL REFERENCES items (id),
    extracted_value TEXT,
    corrected_value TEXT,
    calendar TEXT NOT NULL,
    caldav_uid TEXT,
    removed_externally BOOLEAN NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_deadlines_item ON deadlines (item_id);

CREATE TABLE proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_key TEXT NOT NULL,
    field TEXT NOT NULL,
    proposed_value TEXT NOT NULL,
    evidence_urls TEXT NOT NULL,       -- JSON list
    status TEXT NOT NULL CHECK (status IN ('pending', 'accepted', 'rejected')) DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (record_key, field, proposed_value)
);

CREATE TABLE missed_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    watch_id TEXT NOT NULL,
    diagnosis TEXT CHECK (diagnosis IN ('coverage_gap', 'filter_gap', 'scoring_gap', 'extraction_gap')),
    created_at TEXT NOT NULL
);

CREATE TABLE source_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    note TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending', 'dry_run', 'confirmed', 'rejected')) DEFAULT 'pending',
    outcome TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT REFERENCES items (id),
    channel TEXT NOT NULL,
    message TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    delivered BOOLEAN NOT NULL DEFAULT 0,
    retry_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_alerts_item ON alerts (item_id);
