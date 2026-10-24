"""Short stable hashes used to version data and configuration."""

import hashlib
import json


def fingerprint(*parts: object) -> str:
    """Return a short hash of JSON-serializable parts; equal inputs give equal hashes."""
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:12]
