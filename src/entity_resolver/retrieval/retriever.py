"""Nominate and rank candidate entities for an input name."""

from collections.abc import Sequence

from entity_resolver.models import Candidate, MatchKind
from entity_resolver.normalize import compact
from entity_resolver.retrieval.matchers import DEFAULT_MATCHERS, NameMatcher
from entity_resolver.store.repository import KnowledgeSnapshot


class CandidateRetriever:
    def __init__(
        self,
        snapshot: KnowledgeSnapshot,
        top_k: int,
        matchers: Sequence[NameMatcher] = DEFAULT_MATCHERS,
    ) -> None:
        self._entities = snapshot.entities
        self._top_k = top_k
        self._matchers = sorted(matchers, key=lambda matcher: matcher.kind)
        self._names = tuple(
            (entity_id, compact(alias))
            for alias, entity_ids in snapshot.alias_index.items()
            for entity_id in entity_ids
        )

    def retrieve(self, normalized_query: str) -> tuple[Candidate, ...]:
        """Return up to top_k candidates, best first, or none when exact matches overflow K."""
        query = compact(normalized_query)
        best: dict[str, Candidate] = {}
        # PRODUCTION: this is a linear scan over every name; benchmark at catalog scale.
        for entity_id, name in self._names:
            candidate = self._match(entity_id, query, name)
            current = best.get(entity_id)
            if candidate is not None and (current is None or candidate.sort_key < current.sort_key):
                best[entity_id] = candidate

        ranked = sorted(best.values(), key=lambda candidate: candidate.sort_key)
        exact_count = sum(candidate.kind is MatchKind.EXACT for candidate in ranked)
        if exact_count > self._top_k:
            # Choosing an arbitrary subset of equally exact matches would hide the ambiguity.
            return ()
        return tuple(ranked[: self._top_k])

    def _match(self, entity_id: str, query: str, name: str) -> Candidate | None:
        for matcher in self._matchers:
            if matcher.matches(query, name):
                return Candidate(
                    self._entities[entity_id], matcher.kind, abs(len(name) - len(query))
                )
        return None
