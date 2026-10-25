"""Interactive session: resolve names one at a time with one resolver, so its cache is visible."""

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from entity_resolver.domain import MatchType
from entity_resolver.errors import ResolverError
from entity_resolver.resolver import Resolution, Resolver

EXIT_WORDS = frozenset({"exit", "quit"})


@dataclass(slots=True)
class SessionStats:
    """Counts of where each answer in a session came from."""

    requests: int = 0
    exact: int = 0
    cache_hits: int = 0
    llm_calls: int = 0
    no_candidates: int = 0
    errors: int = 0


def run_session(
    resolver: Resolver,
    lines: Iterable[str],
    write: Callable[[str], None],
    cost_per_llm_call: float,
) -> SessionStats:
    """Resolve each line until an exit word or the end of input, then print a summary.

    Errors are reported and the session continues; they are never cached.
    """
    stats = SessionStats()
    for line in lines:
        name = line.strip()
        if name.casefold() in EXIT_WORDS:
            break
        if not name:
            continue
        stats.requests += 1
        started = time.perf_counter()
        try:
            resolution = resolver.explain(name)
        except ResolverError as error:
            stats.errors += 1
            write(f"  error: {error}")
            continue
        elapsed_ms = (time.perf_counter() - started) * 1000
        _count(stats, resolution)
        answer = resolution.result.canonical_name or "unknown"
        write(f"  {answer:<34} {describe_source(resolution):<44} {elapsed_ms:>9,.1f} ms")
    _write_summary(stats, write, cost_per_llm_call)
    return stats


def describe_source(resolution: Resolution) -> str:
    """Explain where an answer came from: exact alias, cache, LLM, or no candidates."""
    result = resolution.result
    if result.match_type is MatchType.EXACT:
        return "exact alias"
    if resolution.cache_hit:
        return "cache"
    selection = resolution.selection
    if selection is None:
        return "no candidates (no LLM call)"
    if selection.candidate_id is None:
        return "llm: no match"
    if result.match_type is MatchType.LLM:
        return f"llm: score {selection.match_score:.2f}"
    picked = next(
        c.entity.canonical_name
        for c in resolution.candidates
        if c.entity.id == selection.candidate_id
    )
    return f"llm: {picked} at {selection.match_score:.2f}, below threshold"


def _count(stats: SessionStats, resolution: Resolution) -> None:
    if resolution.result.match_type is MatchType.EXACT:
        stats.exact += 1
    elif resolution.cache_hit:
        stats.cache_hits += 1
    elif resolution.selection is not None:
        stats.llm_calls += 1
    else:
        stats.no_candidates += 1


def _write_summary(stats: SessionStats, write: Callable[[str], None], cost: float) -> None:
    write("")
    write(
        f"{stats.requests} requests: {stats.exact} exact, {stats.cache_hits} cache hits, "
        f"{stats.llm_calls} LLM calls, {stats.no_candidates} without candidates, "
        f"{stats.errors} errors"
    )
    # A cached unknown may never have needed the LLM, so savings are an upper bound.
    write(
        f"Estimated LLM cost ${stats.llm_calls * cost:.4f}; "
        f"cache hits saved up to ${stats.cache_hits * cost:.4f} (at ${cost} per call)"
    )
