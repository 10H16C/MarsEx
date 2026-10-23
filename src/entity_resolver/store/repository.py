"""Load an immutable in-memory snapshot of the knowledge base."""

from collections import defaultdict
from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from entity_resolver.fingerprint import fingerprint
from entity_resolver.models import Entity
from entity_resolver.store.database import connect


@dataclass(frozen=True, slots=True)
class KnowledgeSnapshot:
    entities: Mapping[str, Entity]
    alias_index: Mapping[str, tuple[str, ...]]
    """Normalized alias -> entity IDs sharing it, sorted."""
    fingerprint: str


def load_snapshot(db_path: Path) -> KnowledgeSnapshot:
    if not db_path.exists():
        raise FileNotFoundError(f"Knowledge base {db_path} not found; run the import command.")
    with closing(connect(db_path)) as connection:
        entity_rows: list[tuple[str, str, str, str]] = connection.execute(
            "SELECT id, canonical_name, vendor, description FROM entities ORDER BY id"
        ).fetchall()
        alias_rows: list[tuple[str, str]] = connection.execute(
            "SELECT normalized_alias, entity_id FROM aliases ORDER BY normalized_alias, entity_id"
        ).fetchall()

    aliases_by_entity: defaultdict[str, list[str]] = defaultdict(list)
    ids_by_alias: defaultdict[str, list[str]] = defaultdict(list)
    for alias, entity_id in alias_rows:
        aliases_by_entity[entity_id].append(alias)
        ids_by_alias[alias].append(entity_id)

    entities = {
        entity_id: Entity(
            entity_id, canonical_name, vendor, description, tuple(aliases_by_entity[entity_id])
        )
        for entity_id, canonical_name, vendor, description in entity_rows
    }
    return KnowledgeSnapshot(
        entities=entities,
        alias_index={alias: tuple(ids) for alias, ids in ids_by_alias.items()},
        fingerprint=fingerprint(entity_rows, alias_rows),
    )
