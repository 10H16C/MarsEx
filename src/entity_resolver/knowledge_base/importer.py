"""Validate seed JSON and write it to SQLite in one transaction."""

import sqlite3
from collections.abc import Iterable, Sequence
from contextlib import closing
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, TypeAdapter

from entity_resolver.errors import SeedValidationError
from entity_resolver.knowledge_base.database import connect
from entity_resolver.steps.normalize import normalize

type NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class SeedEntity(BaseModel):
    """One product record in seed JSON; blank strings are rejected."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: NonEmpty
    canonical_name: NonEmpty
    vendor: NonEmpty
    description: NonEmpty
    aliases: tuple[NonEmpty, ...] = ()


_SEED = TypeAdapter(list[SeedEntity])


def import_seed(seed_path: Path, db_path: Path) -> int:
    """Import the full catalog from seed JSON and return the number of entities."""
    entities = _SEED.validate_json(seed_path.read_bytes())
    _validate(entities)
    alias_rows = sorted(
        {(normalize(name), entity.id) for entity in entities for name in _names(entity)}
    )
    with closing(connect(db_path)) as connection, connection:
        _reject_removed_ids(connection, {entity.id for entity in entities})
        connection.executemany(
            """
            INSERT INTO entities (id, canonical_name, vendor, description) VALUES (?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                canonical_name = excluded.canonical_name,
                vendor = excluded.vendor,
                description = excluded.description
            """,
            [(e.id, e.canonical_name, e.vendor, e.description) for e in entities],
        )
        connection.execute("DELETE FROM aliases")
        connection.executemany(
            "INSERT INTO aliases (normalized_alias, entity_id) VALUES (?, ?)", alias_rows
        )
    return len(entities)


def _names(entity: SeedEntity) -> tuple[str, ...]:
    """Canonical names are aliases too, so resolving a returned name is idempotent."""
    return (entity.canonical_name, *entity.aliases)


def _validate(entities: Sequence[SeedEntity]) -> None:
    _unique_owners("Entity id", ((e.id, e.id) for e in entities))
    canonical_owner = _unique_owners(
        "Canonical name", ((normalize(e.canonical_name), e.id) for e in entities)
    )
    for entity in entities:
        for alias in entity.aliases:
            owner = canonical_owner.get(normalize(alias))
            if owner not in (None, entity.id):
                raise SeedValidationError(
                    f"Alias {alias!r} of {entity.id} is the canonical name of {owner}"
                )


def _unique_owners(label: str, pairs: Iterable[tuple[str, str]]) -> dict[str, str]:
    owners: dict[str, str] = {}
    for key, owner in pairs:
        if key in owners:
            raise SeedValidationError(f"{label} {key!r} is used by {owners[key]} and {owner}")
        owners[key] = owner
    return owners


def _reject_removed_ids(connection: sqlite3.Connection, seed_ids: set[str]) -> None:
    # Canonical IDs are stable. Retiring an entity would need a deprecation record that maps
    # old IDs to replacements; that workflow is out of scope, so removal is rejected.
    existing: set[str] = {row[0] for row in connection.execute("SELECT id FROM entities")}
    removed = sorted(existing - seed_ids)
    if removed:
        raise SeedValidationError(f"Seed removes existing entity ids: {', '.join(removed)}")
