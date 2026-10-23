"""Metrics computed from recorded observations, without further LLM calls."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from entity_resolver.config import Settings
from entity_resolver.evaluation.runner import Observation
from entity_resolver.models import MatchType

SWEEP_THRESHOLDS = tuple(step / 20 for step in range(21))


@dataclass(frozen=True, slots=True)
class ThresholdPoint:
    threshold: float
    precision: float
    recall: float
    f1: float
    false_acceptance: float
    """Share of inputs that should be unknown but were resolved."""


@dataclass(frozen=True, slots=True)
class Report:
    pipeline_version: str
    observations: int
    at_configured_threshold: ThresholdPoint
    recommended_threshold: ThresholdPoint | None
    candidate_recall_at_k: float
    repeat_agreement: float
    latency_p50_ms: float
    latency_p95_ms: float
    llm_call_rate: float
    mean_llm_call_cost_usd: float
    daily_cost_usd_no_cache_hits: float
    daily_cost_usd_at_cache_hit_rate: float
    sweep: tuple[ThresholdPoint, ...]


def predicted_id(observation: Observation, threshold: float) -> str | None:
    """The prediction the resolver would make at another threshold, from the recorded score."""
    selection = observation.resolution.selection
    if selection is None:
        return observation.resolution.result.canonical_id
    return selection.accepted_id(threshold)


def threshold_point(observations: Sequence[Observation], threshold: float) -> ThresholdPoint:
    true_pos = false_pos = false_neg = negatives = accepted_negatives = 0
    for observation in observations:
        expected = observation.record.expected_entity_id
        predicted = predicted_id(observation, threshold)
        if predicted is not None:
            if predicted == expected:
                true_pos += 1
            else:
                false_pos += 1
        if expected is not None and predicted != expected:
            false_neg += 1
        if expected is None:
            negatives += 1
            accepted_negatives += predicted is not None
    precision = _ratio(true_pos, true_pos + false_pos)
    recall = _ratio(true_pos, true_pos + false_neg)
    return ThresholdPoint(
        threshold=threshold,
        precision=precision,
        recall=recall,
        f1=_ratio(2 * precision * recall, precision + recall),
        false_acceptance=_ratio(accepted_negatives, negatives),
    )


def summarize(
    observations: Sequence[Observation],
    settings: Settings,
    *,
    precision_target: float,
    requests_per_day: int,
    cache_hit_rate: float,
) -> Report:
    sweep = tuple(threshold_point(observations, t) for t in SWEEP_THRESHOLDS)
    eligible = [point for point in sweep if point.precision >= precision_target]
    llm_calls = [o.resolution.selection for o in observations if o.resolution.selection]
    total_cost = (
        sum(
            s.input_tokens * settings.input_price_per_mtok
            + s.output_tokens * settings.output_price_per_mtok
            for s in llm_calls
        )
        / 1_000_000
    )
    mean_call_cost = _ratio(total_cost, len(llm_calls))
    llm_call_rate = _ratio(len(llm_calls), len(observations))
    # The dataset's mix of exact and unseen inputs is not real traffic; treat this as a template.
    daily_no_hits = requests_per_day * llm_call_rate * mean_call_cost
    latencies_ms = sorted(o.latency_seconds * 1000 for o in observations)
    return Report(
        pipeline_version=observations[0].resolution.result.pipeline_version,
        observations=len(observations),
        at_configured_threshold=threshold_point(observations, settings.llm_score_threshold),
        recommended_threshold=max(eligible, key=lambda p: (p.recall, p.precision), default=None),
        candidate_recall_at_k=_candidate_recall(observations),
        repeat_agreement=_repeat_agreement(observations),
        latency_p50_ms=_percentile(latencies_ms, 0.50),
        latency_p95_ms=_percentile(latencies_ms, 0.95),
        llm_call_rate=llm_call_rate,
        mean_llm_call_cost_usd=mean_call_cost,
        daily_cost_usd_no_cache_hits=daily_no_hits,
        daily_cost_usd_at_cache_hit_rate=daily_no_hits * (1 - cache_hit_rate),
        sweep=sweep,
    )


def _candidate_recall(observations: Sequence[Observation]) -> float:
    """Share of answerable inputs that reached retrieval whose answer was nominated."""
    retrieved = [
        o
        for o in observations
        if o.record.expected_entity_id is not None
        and o.resolution.result.match_type is not MatchType.EXACT
    ]
    hits = sum(
        o.record.expected_entity_id in {c.entity.id for c in o.resolution.candidates}
        for o in retrieved
    )
    return _ratio(hits, len(retrieved))


def _repeat_agreement(observations: Sequence[Observation]) -> float:
    """Share of inputs that got the same answer in every uncached repeat."""
    answers: defaultdict[str, set[str | None]] = defaultdict(set)
    for observation in observations:
        answers[observation.record.input].add(observation.resolution.result.canonical_id)
    return _ratio(sum(len(ids) == 1 for ids in answers.values()), len(answers))


def _percentile(sorted_values: Sequence[float], fraction: float) -> float:
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, round(fraction * (len(sorted_values) - 1)))
    return sorted_values[index]


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0
