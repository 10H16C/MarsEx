"""Replay a synthetic request stream to measure what the result cache saves.

How often names repeat in real traffic is unknown, so the stream's repetition (Zipf skew)
is an assumption and the results are scenarios, not forecasts. A free stand-in replaces the
LLM; cost uses a per-call price measured with the evaluate command.
PRODUCTION: replay a sample of real extracted names instead of a synthetic stream.
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass, replace
from itertools import accumulate
from pathlib import Path

from entity_resolver.config import Settings
from entity_resolver.domain import Candidate, Selection
from entity_resolver.knowledge_base.snapshot import load_snapshot
from entity_resolver.setup import build_resolver

_SECONDS_PER_DAY = 24 * 60 * 60


class SimulatedClock:
    """Advances a fixed step per request, so cache expiry follows the simulated request rate."""

    def __init__(self, seconds_per_request: float) -> None:
        self._seconds_per_request = seconds_per_request
        self._now = 0.0

    def tick(self) -> None:
        self._now += self._seconds_per_request

    def __call__(self) -> float:
        return self._now


class CountingSelector:
    """Free LLM stand-in: accepts the top candidate and counts calls."""

    version = "simulated"

    def __init__(self) -> None:
        self.calls = 0

    def select(self, query: str, candidates: Sequence[Candidate]) -> Selection:
        self.calls += 1
        return Selection(candidates[0].entity.id, 1.0)


@dataclass(frozen=True, slots=True)
class CacheScenario:
    cache_max_bytes: int
    cache_hit_rate: float
    llm_calls: int
    cost_usd: float
    daily_cost_usd: float
    daily_savings_usd: float
    """Compared with the first scenario in the run (normally cache size 0)."""


@dataclass(frozen=True, slots=True)
class SimulationReport:
    requests: int
    distinct_names_requested: int
    skew: float
    requests_per_day: int
    cost_per_llm_call_usd: float
    scenarios: tuple[CacheScenario, ...]


def build_name_pool(aliases: Sequence[str], size: int, rng: random.Random) -> list[str]:
    """Unseen variants of known names. Each contains a stored alias, so it reaches the LLM."""
    pool = [f"{aliases[i % len(aliases)]} instance {i // len(aliases)}" for i in range(size)]
    rng.shuffle(pool)
    return pool


def request_stream(
    pool: Sequence[str], requests: int, skew: float, rng: random.Random
) -> list[str]:
    """Draw requests where the name at rank r is requested in proportion to 1 / r**skew."""
    cumulative = list(accumulate(1 / rank**skew for rank in range(1, len(pool) + 1)))
    return rng.choices(pool, cum_weights=cumulative, k=requests)


def simulate(
    db_path: Path,
    settings: Settings,
    *,
    requests: int,
    unique_names: int,
    skew: float,
    cache_sizes: Sequence[int],
    cost_per_llm_call: float,
    requests_per_day: int,
    seed: int,
) -> SimulationReport:
    rng = random.Random(seed)
    pool = build_name_pool(sorted(load_snapshot(db_path).alias_index), unique_names, rng)
    stream = request_stream(pool, requests, skew, rng)
    runs = [
        _run(db_path, replace(settings, cache_max_bytes=size), stream, requests_per_day)
        for size in cache_sizes
    ]
    daily_costs = [
        requests_per_day * (calls / len(stream)) * cost_per_llm_call for _, calls in runs
    ]
    scenarios = tuple(
        CacheScenario(
            cache_max_bytes=size,
            cache_hit_rate=hits / len(stream),
            llm_calls=calls,
            cost_usd=calls * cost_per_llm_call,
            daily_cost_usd=daily_cost,
            daily_savings_usd=daily_costs[0] - daily_cost,
        )
        for size, (hits, calls), daily_cost in zip(cache_sizes, runs, daily_costs, strict=True)
    )
    return SimulationReport(
        requests=len(stream),
        distinct_names_requested=len(set(stream)),
        skew=skew,
        requests_per_day=requests_per_day,
        cost_per_llm_call_usd=cost_per_llm_call,
        scenarios=scenarios,
    )


def _run(
    db_path: Path, settings: Settings, stream: Sequence[str], requests_per_day: int
) -> tuple[int, int]:
    """Return (cache hits, LLM calls) for one pass over the stream with a fresh cache."""
    clock = SimulatedClock(_SECONDS_PER_DAY / requests_per_day)
    selector = CountingSelector()
    resolver = build_resolver(db_path, settings, selector, clock)
    hits = 0
    for name in stream:
        clock.tick()
        hits += resolver.explain(name).cache_hit
    return hits, selector.calls
