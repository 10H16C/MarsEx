"""Text normalization shared by importing, exact lookup, and candidate matching."""

import re

_WHITESPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Casefold and collapse whitespace; punctuation is preserved."""
    return _WHITESPACE.sub(" ", text).strip().casefold()


def compact(normalized: str) -> str:
    """Remove spaces from normalized text for substring and subsequence matching."""
    return normalized.replace(" ", "")
