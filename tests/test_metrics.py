import pytest

from entity_resolver.config import Settings
from entity_resolver.evaluation.dataset import EvalRecord
from entity_resolver.evaluation.metrics import summarize, threshold_point
from entity_resolver.evaluation.runner import Observation
from entity_resolver.models import Entity, MatchType, ResolverResult, Selection
from entity_resolver.resolver import Resolution

_SHAREPOINT = Entity("sp", "Microsoft SharePoint", "Microsoft", "description", ())


def _observation(
    expected: str | None, selection: Selection | None, latency: float = 0.1
) -> Observation:
    result = (
        ResolverResult.resolved(_SHAREPOINT, MatchType.EXACT, 1.0, "v1")
        if selection is None
        else ResolverResult.unknown("v1")
    )
    record = EvalRecord(input=f"in-{expected}", expected_entity_id=expected, case_type="test")
    return Observation(record, Resolution(result, (), selection), latency)


def test_threshold_point_counts_hits_errors_and_false_acceptance() -> None:
    observations = [
        _observation("sp", None),  # exact hit
        _observation("sp", Selection("sp", 0.9)),  # LLM hit at 0.8
        _observation("other", Selection("sp", 0.9)),  # wrong product: FP and FN
        _observation(None, Selection("sp", 0.7)),  # rejected at 0.8, accepted at 0.5
        _observation("sp", Selection(None, 0.0)),  # miss
    ]
    strict = threshold_point(observations, 0.8)
    assert (strict.precision, strict.recall, strict.false_acceptance) == pytest.approx(
        (2 / 3, 2 / 4, 0.0)
    )
    loose = threshold_point(observations, 0.5)
    assert (loose.precision, loose.false_acceptance) == pytest.approx((2 / 4, 1.0))


def test_summary_reports_cost_and_recommended_threshold() -> None:
    observations = [
        _observation("sp", None),
        _observation("sp", Selection("sp", 0.9, input_tokens=1_000, output_tokens=100)),
    ]
    report = summarize(
        observations,
        Settings(input_price_per_mtok=4.0, output_price_per_mtok=20.0),
        precision_target=0.95,
        requests_per_day=1_000,
        cache_hit_rate=0.5,
    )
    assert report.mean_llm_call_cost_usd == pytest.approx(0.006)
    assert report.llm_call_rate == pytest.approx(0.5)
    assert report.daily_cost_usd_no_cache_hits == pytest.approx(3.0)
    assert report.daily_cost_usd_at_cache_hit_rate == pytest.approx(1.5)
    assert report.recommended_threshold is not None
    assert report.recommended_threshold.recall == 1.0
