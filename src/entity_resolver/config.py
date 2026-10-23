"""Resolver settings."""

from dataclasses import dataclass
from typing import Literal

type Effort = Literal["low", "medium", "high", "xhigh", "max"]


@dataclass(frozen=True, slots=True)
class Settings:
    # Placeholders until tuned on data/eval/dev.json; freeze them before running the test set.
    top_k: int = 10
    llm_score_threshold: float = 0.8

    cache_max_bytes: int = 10_000_000
    cache_ttl_seconds: float = 24 * 60 * 60

    model: str = "claude-opus-5-5"
    effort: Effort = "low"
    # Server-side fallback can answer with another model, which affects consistency runs.
    use_refusal_fallback: bool = True

    # USD per million tokens, used only for cost reporting.
    input_price_per_mtok: float = 4.0
    output_price_per_mtok: float = 20.0
