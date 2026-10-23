"""Port for candidate selection, so the resolver does not depend on a provider SDK."""

from collections.abc import Sequence
from typing import Protocol

from entity_resolver.models import Candidate, Selection


class CandidateSelector(Protocol):
    @property
    def version(self) -> str:
        """Identifies model and prompt configuration; part of the pipeline version."""
        ...

    def select(self, query: str, candidates: Sequence[Candidate]) -> Selection:
        """Pick one candidate or none. Raise ResolverError subclasses on failure."""
        ...
