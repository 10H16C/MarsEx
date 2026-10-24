"""Run a labeled dataset through the resolver and record what happened."""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from entity_resolver.resolver import Resolution, Resolver
from entity_resolver.tools.evaluation.dataset import EvalRecord


@dataclass(frozen=True, slots=True)
class Observation:
    record: EvalRecord
    resolution: Resolution
    latency_seconds: float


def run(
    records: Sequence[EvalRecord], make_resolver: Callable[[], Resolver], repeats: int
) -> list[Observation]:
    """Each repeat uses a fresh resolver, so its cache is empty and every LLM decision is new.

    Provider errors stop the run: they are infrastructure failures, not predictions.
    PRODUCTION: schedule this against a frozen test set and alert on metric regressions.
    """
    observations: list[Observation] = []
    for _ in range(repeats):
        resolver = make_resolver()
        for record in records:
            started = time.perf_counter()
            resolution = resolver.explain(record.input)
            observations.append(Observation(record, resolution, time.perf_counter() - started))
    return observations
