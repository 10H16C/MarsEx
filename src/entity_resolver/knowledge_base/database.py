"""SQLite connection setup shared by the importer and the snapshot loader."""

import sqlite3
from importlib.resources import files
from pathlib import Path

_SCHEMA = files("entity_resolver.knowledge_base").joinpath("schema.sql").read_text(encoding="utf-8")


def connect(db_path: Path) -> sqlite3.Connection:
    """Open the database with foreign keys enforced, creating the tables if needed."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(_SCHEMA)
    return connection
