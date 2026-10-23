CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    vendor TEXT NOT NULL,
    description TEXT NOT NULL
);

-- A shared alias is several rows, one per entity.
CREATE TABLE IF NOT EXISTS aliases (
    normalized_alias TEXT NOT NULL,
    entity_id TEXT NOT NULL REFERENCES entities (id),
    PRIMARY KEY (normalized_alias, entity_id)
);
