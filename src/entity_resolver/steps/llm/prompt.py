"""Prompt text and request rendering for candidate selection."""

import json
from collections.abc import Sequence

from entity_resolver.domain import Candidate

# Bump when render_request changes shape; SYSTEM_PROMPT is versioned by its text.
REQUEST_FORMAT_VERSION = 1

SYSTEM_PROMPT = """\
You resolve technology names extracted from threat-intelligence reports to products in a catalog.

You receive an input name and candidate products. Each candidate has an id, canonical name, \
vendor, known aliases, and a short description.

Pick the candidate that is the same product the input names.
- A related product is not a match: a different edition, module, service, or another product \
from the same vendor is a different product.
- A vendor name alone matches only when people commonly use that vendor name to mean that \
specific product.
- If no candidate is clearly the same product, or several are equally plausible, return null.
- Only return an id from the candidate list.

match_score is your confidence from 0 to 1 that the input names the chosen product. \
When candidate_id is null, set match_score to 0."""


def render_request(query: str, candidates: Sequence[Candidate]) -> str:
    """Render the input and candidates as the JSON user message, in rank order."""
    payload = {
        "input": query,
        "candidates": [
            {
                "id": candidate.entity.id,
                "canonical_name": candidate.entity.canonical_name,
                "vendor": candidate.entity.vendor,
                "aliases": list(candidate.entity.aliases),
                "description": candidate.entity.description,
            }
            for candidate in candidates
        ],
    }
    return json.dumps(payload, ensure_ascii=False)
