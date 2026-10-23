from pathlib import Path

import pytest

from entity_resolver.composition import build_resolver
from entity_resolver.config import Settings
from entity_resolver.resolver import Resolver
from entity_resolver.store.importer import import_seed
from tests.fakes import FakeSelector

SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "seed.json"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "kb.sqlite"
    import_seed(SEED_PATH, path)
    return path


@pytest.fixture
def selector() -> FakeSelector:
    return FakeSelector()


@pytest.fixture
def resolver(db_path: Path, selector: FakeSelector) -> Resolver:
    return build_resolver(db_path, Settings(llm_score_threshold=0.8), selector)
