from pathlib import Path

import pytest

from entity_resolver.domain import MatchType, Selection, Status
from entity_resolver.errors import InvalidSelectionError, SelectorError
from entity_resolver.resolver import Resolver
from entity_resolver.setup import build_resolver
from tests.fakes import FakeSelector


@pytest.mark.parametrize("name", ["AWS", "Amazon Web Services", "aws cloud", "  Amazon   AWS "])
def test_aliases_resolve_to_one_entity_without_llm(
    resolver: Resolver, selector: FakeSelector, name: str
) -> None:
    result = resolver.resolve(name)
    assert (result.canonical_id, result.match_type, result.score) == ("aws", MatchType.EXACT, 1.0)
    assert selector.calls == []


def test_platform_and_its_product_stay_separate(resolver: Resolver) -> None:
    assert resolver.resolve("Amazon Web Services").canonical_id == "aws"
    assert resolver.resolve("AWS EKS").canonical_id == "aws_eks"


@pytest.mark.parametrize(
    ("score", "expected_id"), [(0.95, "ms_sentinel"), (0.8, "ms_sentinel"), (0.5, None)]
)
def test_near_collision_is_decided_by_threshold(
    resolver: Resolver, selector: FakeSelector, score: float, expected_id: str | None
) -> None:
    selector.responses["Sentinel"] = Selection("ms_sentinel", score)
    resolution = resolver.explain("Sentinel")
    assert {"ms_sentinel", "s1_singularity"} <= {c.entity.id for c in resolution.candidates}
    assert resolution.result.canonical_id == expected_id


def test_llm_rejection_returns_unknown(resolver: Resolver) -> None:
    result = resolver.resolve("Sentinel")
    assert (result.status, result.match_type, result.score) == (
        Status.UNKNOWN,
        MatchType.NONE,
        None,
    )


def test_unseen_variant_resolves_through_llm(resolver: Resolver, selector: FakeSelector) -> None:
    selector.responses["Microsoft sp"] = Selection("ms_sharepoint", 0.9)
    result = resolver.resolve("Microsoft sp")
    assert (result.canonical_name, result.match_type) == ("Microsoft SharePoint", MatchType.LLM)
    assert selector.calls[0][0] == "Microsoft sp"


def test_resolving_returned_name_is_idempotent(resolver: Resolver, selector: FakeSelector) -> None:
    selector.responses["Microsoft sp"] = Selection("ms_sharepoint", 0.9)
    first = resolver.resolve("Microsoft sp")
    assert first.canonical_name is not None
    again = resolver.resolve(first.canonical_name)
    assert (again.canonical_id, again.match_type) == (first.canonical_id, MatchType.EXACT)
    assert resolver.resolve("Microsoft sp") == first


def test_cache_hit_reuses_result_without_llm(resolver: Resolver, selector: FakeSelector) -> None:
    selector.responses["Microsoft sp"] = Selection("ms_sharepoint", 0.9)
    first = resolver.explain("Microsoft sp")
    second = resolver.explain("MICROSOFT  SP")
    assert second.cache_hit and second.result == first.result
    assert len(selector.calls) == 1


def test_selection_outside_candidates_is_an_error_and_not_cached(
    resolver: Resolver, selector: FakeSelector
) -> None:
    selector.responses["Sentinel"] = Selection("aws_eks", 0.99)
    for _ in range(2):
        with pytest.raises(InvalidSelectionError):
            resolver.resolve("Sentinel")
    assert len(selector.calls) == 2


def test_score_outside_range_is_an_error(resolver: Resolver, selector: FakeSelector) -> None:
    selector.responses["Sentinel"] = Selection("ms_sentinel", 1.5)
    with pytest.raises(InvalidSelectionError):
        resolver.resolve("Sentinel")


def test_provider_failure_is_an_error_and_not_cached(
    resolver: Resolver, selector: FakeSelector
) -> None:
    selector.error = SelectorError("timeout")
    for _ in range(2):
        with pytest.raises(SelectorError):
            resolver.resolve("Sentinel")
    assert len(selector.calls) == 2


@pytest.mark.parametrize("name", ["", "   ", "zzqx"])
def test_empty_or_unmatched_input_is_unknown_without_llm(
    resolver: Resolver, selector: FakeSelector, name: str
) -> None:
    assert resolver.resolve(name).status is Status.UNKNOWN
    assert selector.calls == []


def test_same_data_gives_same_pipeline_version(db_path: Path) -> None:
    first = build_resolver(db_path, selector=FakeSelector()).resolve("AWS")
    second = build_resolver(db_path, selector=FakeSelector()).resolve("AWS")
    assert first == second


def test_selector_change_gives_new_pipeline_version(db_path: Path) -> None:
    original = build_resolver(db_path, selector=FakeSelector()).resolve("AWS")
    changed = build_resolver(db_path, selector=FakeSelector(version="other")).resolve("AWS")
    assert original.pipeline_version != changed.pipeline_version
