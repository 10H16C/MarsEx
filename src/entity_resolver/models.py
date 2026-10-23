"""Domain objects passed between the resolver stages."""

from dataclasses import asdict, dataclass
from enum import IntEnum, StrEnum


@dataclass(frozen=True, slots=True)
class Entity:
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
    entity: Entity
    kind: MatchKind
    unmatched_chars: int

    @property
    def sort_key(self) -> tuple[int, int, str]:
        return (self.kind, self.unmatched_chars, self.entity.id)


@dataclass(frozen=True, slots=True)
class Selection:
    """Raw LLM decision. The score is a model judgment, not a calibrated probability."""

    candidate_id: str | None
    match_score: float
    input_tokens: int = 0
    output_tokens: int = 0

    def accepted_id(self, threshold: float) -> str | None:
        if self.candidate_id is not None and self.match_score >= threshold:
            return self.candidate_id
        return None


class Status(StrEnum):
    RESOLVED = "resolved"
    UNKNOWN = "unknown"


class MatchType(StrEnum):
    EXACT = "exact"
    LLM = "llm"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class ResolverResult:
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
        return cls(
            Status.RESOLVED, entity.id, entity.canonical_name, match_type, score, pipeline_version
        )

    @classmethod
    def unknown(cls, pipeline_version: str) -> "ResolverResult":
        return cls(Status.UNKNOWN, None, None, MatchType.NONE, None, pipeline_version)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
