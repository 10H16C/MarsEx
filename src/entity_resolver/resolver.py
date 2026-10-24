"""Resolution pipeline: normalize, exact alias, cache, candidates, LLM selection, threshold."""

from collections.abc import Sequence
from dataclasses import dataclass

from entity_resolver.domain import Candidate, Entity, MatchType, ResolverResult, Selection
from entity_resolver.errors import InvalidSelectionError
from entity_resolver.knowledge_base.snapshot import KnowledgeSnapshot
from entity_resolver.steps.cache import BoundedTTLCache
from entity_resolver.steps.candidates.retriever import CandidateRetriever
from entity_resolver.steps.llm.selector import CandidateSelector
from entity_resolver.steps.normalize import normalize

type CacheKey = tuple[str, str]
type ResultCache = BoundedTTLCache[CacheKey, ResolverResult]


@dataclass(frozen=True, slots=True)
class Resolution:
    """A result plus the evidence behind it, for evaluation and debugging."""

    result: ResolverResult
    candidates: tuple[Candidate, ...] = ()
    selection: Selection | None = None
    cache_hit: bool = False


class Resolver:
    """Resolves technology names to canonical products. Build it with setup.build_resolver."""

    def __init__(
        self,
        snapshot: KnowledgeSnapshot,
        retriever: CandidateRetriever,
        selector: CandidateSelector,
        cache: ResultCache,
        score_threshold: float,
        pipeline_version: str,
    ) -> None:
        self._snapshot = snapshot
        self._retriever = retriever
        self._selector = selector
        self._cache = cache
        self._score_threshold = score_threshold
        self._pipeline_version = pipeline_version

    def resolve(self, name: str) -> ResolverResult:
        """Resolve a raw name to a product, or return unknown.

        Raises ResolverError subclasses when the LLM request fails or breaks the contract.
        """
        return self.explain(name).result

    def explain(self, name: str) -> Resolution:
        """Resolve a raw name and also return the candidates and LLM selection behind it."""
        # PRODUCTION: emit per-stage counters (exact, cache hit, no candidates, LLM) and latency.
        query = normalize(name)
        if not query:
            return Resolution(ResolverResult.unknown(self._pipeline_version))

        exact_ids = self._snapshot.alias_index.get(query, ())
        if len(exact_ids) == 1:
            entity = self._snapshot.entities[exact_ids[0]]
            return Resolution(
                ResolverResult.resolved(entity, MatchType.EXACT, 1.0, self._pipeline_version)
            )

        key = (self._pipeline_version, query)
        cached = self._cache.get(key)
        if cached is not None:
            return Resolution(cached, cache_hit=True)

        resolution = self._decide(name.strip(), query)
        # Only validated results reach this line; provider and contract errors propagate uncached.
        self._cache.put(key, resolution.result)
        return resolution

    def _decide(self, raw_name: str, query: str) -> Resolution:
        candidates = self._retriever.retrieve(query)
        if not candidates:
            return Resolution(ResolverResult.unknown(self._pipeline_version))

        selection = self._selector.select(raw_name, candidates)
        entity = self._accepted_entity(selection, candidates)
        # PRODUCTION: send unknowns and low-score selections to a human-review queue. Reviewed
        # decisions may become curated aliases; LLM decisions never become aliases on their own.
        result = (
            ResolverResult.resolved(
                entity, MatchType.LLM, selection.match_score, self._pipeline_version
            )
            if entity is not None
            else ResolverResult.unknown(self._pipeline_version)
        )
        return Resolution(result, candidates, selection)

    def _accepted_entity(
        self, selection: Selection, candidates: Sequence[Candidate]
    ) -> Entity | None:
        if not 0.0 <= selection.match_score <= 1.0:
            raise InvalidSelectionError(f"match_score {selection.match_score} is outside 0-1")
        offered = {candidate.entity.id: candidate.entity for candidate in candidates}
        if selection.candidate_id is not None and selection.candidate_id not in offered:
            raise InvalidSelectionError(f"{selection.candidate_id!r} was not a candidate")
        accepted_id = selection.accepted_id(self._score_threshold)
        return offered[accepted_id] if accepted_id is not None else None
