"""Test double for the LLM port."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from entity_resolver.domain import Candidate, Selection
from entity_resolver.errors import ResolverError

NO_MATCH = Selection(candidate_id=None, match_score=0.0)


@dataclass
class FakeSelector:
    """Returns scripted selections by raw input and records every call."""

    responses: dict[str, Selection] = field(default_factory=dict[str, Selection])
    error: ResolverError | None = None
    calls: list[tuple[str, tuple[Candidate, ...]]] = field(
        default_factory=list[tuple[str, tuple[Candidate, ...]]]
    )
    version: str = "fake"

    def select(self, query: str, candidates: Sequence[Candidate]) -> Selection:
        self.calls.append((query, tuple(candidates)))
        if self.error is not None:
            raise self.error
        return self.responses.get(query, NO_MATCH)
