"""Domain objects passed between the resolver stages."""

from dataclasses import asdict, dataclass
from enum import IntEnum, StrEnum


@dataclass(frozen=True, slots=True)
class Entity:
    """A catalog product with its stable ID and normalized aliases."""

    id: str
    canonical_name: str
    vendor: str
    description: str
    aliases: tuple[str, ...]


class MatchKind(IntEnum):
    """Candidate match strength; lower values rank first."""

    EXACT = 0
    SUBSTRING = 1
    SUBSEQUENCE = 2


@dataclass(frozen=True, slots=True)
class Candidate:
    """A product nominated by name matching, with how strongly its name matched."""

    entity: Entity
    kind: MatchKind
    unmatched_chars: int

    @property
    def sort_key(self) -> tuple[int, int, str]:
        """Rank by match strength, then fewer unmatched characters, then entity ID."""
        return (self.kind, self.unmatched_chars, self.entity.id)


@dataclass(frozen=True, slots=True)
class Selection:
    """Raw LLM decision. The score is a model judgment, not a calibrated probability."""

    candidate_id: str | None
    match_score: float
    input_tokens: int = 0
    output_tokens: int = 0

    def accepted_id(self, threshold: float) -> str | None:
        """Return the chosen ID if it meets the threshold, otherwise None."""
        if self.candidate_id is not None and self.match_score >= threshold:
            return self.candidate_id
        return None


class Status(StrEnum):
    """Whether an input was resolved to a product."""

    RESOLVED = "resolved"
    UNKNOWN = "unknown"


class MatchType(StrEnum):
    """How a result was decided: exact alias, LLM selection, or no match."""

    EXACT = "exact"
    LLM = "llm"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class ResolverResult:
    """The response of resolve(). Canonical fields and score are None when unknown."""

    status: Status
    canonical_id: str | None
    canonical_name: str | None
    match_type: MatchType
    score: float | None
    pipeline_version: str

    @classmethod
    def resolved(
        cls, entity: Entity, match_type: MatchType, score: float, pipeline_version: str
    ) -> "ResolverResult":
        """Build a result that identifies a product."""
        return cls(
            Status.RESOLVED, entity.id, entity.canonical_name, match_type, score, pipeline_version
        )

    @classmethod
    def unknown(cls, pipeline_version: str) -> "ResolverResult":
        """Build a result for an input that matches no product."""
        return cls(Status.UNKNOWN, None, None, MatchType.NONE, None, pipeline_version)

    def to_dict(self) -> dict[str, object]:
        """Return the result as a JSON-serializable dict."""
        return asdict(self)
