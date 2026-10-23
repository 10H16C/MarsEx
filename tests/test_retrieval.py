from pathlib import Path

import pytest

from entity_resolver.models import Entity, MatchKind
from entity_resolver.normalize import normalize
from entity_resolver.retrieval.matchers import SubsequenceMatcher, SubstringMatcher
from entity_resolver.retrieval.retriever import CandidateRetriever
from entity_resolver.store.repository import KnowledgeSnapshot, load_snapshot


def _candidate_ids(db_path: Path, name: str, top_k: int = 10) -> list[str]:
    retriever = CandidateRetriever(load_snapshot(db_path), top_k)
    return [candidate.entity.id for candidate in retriever.retrieve(normalize(name))]


@pytest.mark.parametrize(
    ("query", "name", "expected"),
    [("sp", "sharepoint", True), ("ps", "sharepoint", False), ("sharepoint", "sp", False)],
)
def test_subsequence_requires_order(query: str, name: str, expected: bool) -> None:
    assert SubsequenceMatcher().matches(query, name) is expected


def test_substring_matches_in_both_directions() -> None:
    matcher = SubstringMatcher()
    assert matcher.matches("sentinel", "sentinelonesingularity")
    assert matcher.matches("awscloudplatform", "aws")


def test_unseen_abbreviation_nominates_product(db_path: Path) -> None:
    assert "ms_sharepoint" in _candidate_ids(db_path, "Microsoft sp")


def test_near_collision_nominates_both_products(db_path: Path) -> None:
    candidates = _candidate_ids(db_path, "Sentinel")
    assert {"ms_sentinel", "s1_singularity"} <= set(candidates)


def test_vendor_name_nominates_its_products(db_path: Path) -> None:
    assert {"splunk_enterprise", "splunk_es"} <= set(_candidate_ids(db_path, "Splunk"))


def test_name_inside_input_nominates_platform(db_path: Path) -> None:
    assert "aws" in _candidate_ids(db_path, "AWS cloud platform")


def test_product_outranks_platform_for_product_input(db_path: Path) -> None:
    candidates = _candidate_ids(db_path, "AWS EKS cluster")
    assert candidates.index("aws_eks") < candidates.index("aws")


def test_results_are_truncated_to_top_k(db_path: Path) -> None:
    assert len(_candidate_ids(db_path, "s", top_k=3)) == 3


def test_exact_matches_beyond_k_return_no_candidates() -> None:
    entities = {
        entity_id: Entity(entity_id, entity_id, "Vendor", "description", ("shared",))
        for entity_id in ("first", "second")
    }
    snapshot = KnowledgeSnapshot(entities, {"shared": ("first", "second")}, "test")
    retriever = CandidateRetriever(snapshot, top_k=1)
    assert retriever.retrieve("shared") == ()
    assert [c.kind for c in CandidateRetriever(snapshot, top_k=2).retrieve("shared")] == [
        MatchKind.EXACT,
        MatchKind.EXACT,
    ]
