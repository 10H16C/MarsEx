import random
from pathlib import Path

import pytest

from entity_resolver.config import Settings
from entity_resolver.evaluation.simulation import (
    build_name_pool,
    request_stream,
    simulate,
)


def _simulate(db_path: Path, cache_sizes: list[int], **overrides: int) -> list[tuple[int, int]]:
    options = {"requests": 300, "unique_names": 60, "requests_per_day": 1_000_000} | overrides
    report = simulate(
        db_path,
        Settings(),
        requests=options["requests"],
        unique_names=options["unique_names"],
        skew=1.0,
        cache_sizes=cache_sizes,
        cost_per_llm_call=0.01,
        requests_per_day=options["requests_per_day"],
        seed=1,
    )
    return [(s.llm_calls, report.distinct_names_requested) for s in report.scenarios]


def test_name_pool_is_unique_and_reproducible() -> None:
    pool = build_name_pool(["aws", "aws eks"], 5, random.Random(3))
    assert len(set(pool)) == 5
    assert pool == build_name_pool(["aws", "aws eks"], 5, random.Random(3))


def test_skew_makes_the_top_name_dominate() -> None:
    pool = [f"name {i}" for i in range(100)]
    stream = request_stream(pool, 10_000, skew=2.0, rng=random.Random(5))
    assert stream.count(pool[0]) > stream.count(pool[1]) > stream.count(pool[50])


def test_no_cache_calls_llm_for_every_request(db_path: Path) -> None:
    [(calls, _)] = _simulate(db_path, [0])
    assert calls == 300


def test_large_cache_calls_llm_once_per_distinct_name(db_path: Path) -> None:
    [(calls, distinct)] = _simulate(db_path, [10_000_000])
    assert calls == distinct


def test_small_cache_evicts_and_saves_less(db_path: Path) -> None:
    [(small_calls, distinct), (large_calls, _)] = _simulate(db_path, [2_000, 10_000_000])
    assert large_calls == distinct < small_calls < 300


def test_expired_entries_are_called_again(db_path: Path) -> None:
    # 10 requests per day: each request advances 2.4 hours, so 24-hour entries expire.
    [(calls, distinct)] = _simulate(db_path, [10_000_000], requests_per_day=10)
    assert calls > distinct


def test_savings_are_relative_to_first_scenario(db_path: Path) -> None:
    report = simulate(
        db_path,
        Settings(),
        requests=200,
        unique_names=50,
        skew=1.0,
        cache_sizes=[0, 10_000_000],
        cost_per_llm_call=0.01,
        requests_per_day=1_000,
        seed=2,
    )
    baseline, cached = report.scenarios
    assert baseline.daily_cost_usd == pytest.approx(10.0)
    assert baseline.daily_savings_usd == 0
    assert cached.daily_savings_usd == pytest.approx(10.0 - cached.daily_cost_usd)
    assert cached.cache_hit_rate == pytest.approx(1 - cached.llm_calls / 200)
