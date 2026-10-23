import json
from pathlib import Path

import pytest

from entity_resolver.errors import SeedValidationError
from entity_resolver.store.importer import import_seed
from entity_resolver.store.repository import load_snapshot
from tests.conftest import SEED_PATH


def _entity(entity_id: str, name: str, aliases: list[str] | None = None) -> dict[str, object]:
    return {
        "id": entity_id,
        "canonical_name": name,
        "vendor": "Vendor",
        "description": "description",
        "aliases": aliases or [],
    }


def _write_seed(tmp_path: Path, entities: list[dict[str, object]]) -> Path:
    path = tmp_path / "seed.json"
    path.write_text(json.dumps(entities), encoding="utf-8")
    return path


def test_canonical_names_are_stored_as_aliases(db_path: Path) -> None:
    snapshot = load_snapshot(db_path)
    assert snapshot.alias_index["aws eks"] == ("aws_eks",)


def test_reimporting_same_seed_keeps_snapshot_identical(db_path: Path) -> None:
    before = load_snapshot(db_path).fingerprint
    import_seed(SEED_PATH, db_path)
    assert load_snapshot(db_path).fingerprint == before


@pytest.mark.parametrize(
    "entities",
    [
        [_entity("a", "Product A"), _entity("a", "Product B")],
        [_entity("a", "Product A"), _entity("b", "product  a")],
        [_entity("a", "Product A"), _entity("b", "Product B", ["Product A"])],
        [_entity("a", "Product A", ["  "])],
    ],
    ids=["duplicate-id", "duplicate-canonical", "alias-is-other-canonical", "blank-alias"],
)
def test_invalid_seed_is_rejected(tmp_path: Path, entities: list[dict[str, object]]) -> None:
    # SeedValidationError and pydantic's ValidationError are both ValueErrors.
    with pytest.raises(ValueError):
        import_seed(_write_seed(tmp_path, entities), tmp_path / "kb.sqlite")


def test_removing_an_entity_is_rejected_and_rolled_back(tmp_path: Path) -> None:
    db_path = tmp_path / "kb.sqlite"
    import_seed(_write_seed(tmp_path, [_entity("a", "A"), _entity("b", "B")]), db_path)
    with pytest.raises(SeedValidationError):
        import_seed(_write_seed(tmp_path, [_entity("a", "A renamed")]), db_path)
    assert load_snapshot(db_path).entities["a"].canonical_name == "A"
