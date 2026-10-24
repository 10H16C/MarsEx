"""Name-matching strategies, ordered from strongest to weakest.

Both arguments are compacted text: normalized, with spaces removed.
"""

from typing import Protocol

from entity_resolver.domain import MatchKind


class NameMatcher(Protocol):
    """One matching rule. The retriever tries rules from strongest to weakest kind."""

    @property
    def kind(self) -> MatchKind:
        """The match strength this rule reports."""
        ...

    def matches(self, query: str, name: str) -> bool:
        """Return True if the rule considers the query and name a match."""
        ...


class ExactMatcher:
    """Rule for identical names."""

    kind: MatchKind = MatchKind.EXACT

    def matches(self, query: str, name: str) -> bool:
        """The query equals the name."""
        return query == name


class SubstringMatcher:
    """Rule for one name containing the other."""

    kind: MatchKind = MatchKind.SUBSTRING

    def matches(self, query: str, name: str) -> bool:
        """Either contains the other: "sentinel" in "sentinelone", "aws" in "awscloud"."""
        return query in name or name in query


class SubsequenceMatcher:
    """Rule for abbreviations whose letters appear in order inside the name."""

    kind: MatchKind = MatchKind.SUBSEQUENCE

    def matches(self, query: str, name: str) -> bool:
        """The query's characters appear in order, gaps allowed: "sp" in "sharepoint"."""
        remaining = iter(name)
        return all(char in remaining for char in query)


DEFAULT_MATCHERS: tuple[NameMatcher, ...] = (
    ExactMatcher(),
    SubstringMatcher(),
    SubsequenceMatcher(),
)
