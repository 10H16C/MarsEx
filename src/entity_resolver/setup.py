"""Composition root: the only place where resolver components are constructed."""

import json
import time
from collections.abc import Callable
from pathlib import Path

from entity_resolver.config import Settings
from entity_resolver.domain import ResolverResult
from entity_resolver.knowledge_base.snapshot import load_snapshot
from entity_resolver.resolver import CacheKey, Resolver, ResultCache
from entity_resolver.steps.cache import BoundedTTLCache
from entity_resolver.steps.candidates.retriever import CandidateRetriever
from entity_resolver.steps.llm.claude import AnthropicSelector
from entity_resolver.steps.llm.selector import CandidateSelector
from entity_resolver.versioning import fingerprint


def build_resolver(
    db_path: Path,
    settings: Settings | None = None,
    selector: CandidateSelector | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> Resolver:
    settings = settings or Settings()
    selector = selector or AnthropicSelector(settings)
    snapshot = load_snapshot(db_path)
    # Any change to data, retrieval, acceptance, model, or prompt yields a new version,
    # so cached results from an older pipeline are never served.
    pipeline_version = fingerprint(
        snapshot.fingerprint, settings.top_k, settings.llm_score_threshold, selector.version
    )
    cache: ResultCache = BoundedTTLCache(
        settings.cache_max_bytes, settings.cache_ttl_seconds, _entry_size, clock
    )
    return Resolver(
        snapshot=snapshot,
        retriever=CandidateRetriever(snapshot, settings.top_k),
        selector=selector,
        cache=cache,
        score_threshold=settings.llm_score_threshold,
        pipeline_version=pipeline_version,
    )


def _entry_size(key: CacheKey, value: ResolverResult) -> int:
    """Approximate entry size from its serialized form."""
    return len(json.dumps([key, value.to_dict()]).encode())
