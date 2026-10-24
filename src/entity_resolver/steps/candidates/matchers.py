"""Name-matching strategies, ordered from strongest to weakest.

Both arguments are compacted text: normalized, with spaces removed.
"""

from typing import Protocol

from entity_resolver.domain import MatchKind


class NameMatcher(Protocol):
    @property
    def kind(self) -> MatchKind: ...

    def matches(self, query: str, name: str) -> bool: ...


class ExactMatcher:
    kind: MatchKind = MatchKind.EXACT

    def matches(self, query: str, name: str) -> bool:
        return query == name


class SubstringMatcher:
    """Either text contains the other: "sentinel" in "sentinelone", "aws" in "awscloud"."""

    kind: MatchKind = MatchKind.SUBSTRING

    def matches(self, query: str, name: str) -> bool:
        return query in name or name in query


class SubsequenceMatcher:
    """The query's characters appear in order inside the name: "sp" in "sharepoint"."""

    kind: MatchKind = MatchKind.SUBSEQUENCE

    def matches(self, query: str, name: str) -> bool:
        remaining = iter(name)
        return all(char in remaining for char in query)


DEFAULT_MATCHERS: tuple[NameMatcher, ...] = (
    ExactMatcher(),
    SubstringMatcher(),
    SubsequenceMatcher(),
)
