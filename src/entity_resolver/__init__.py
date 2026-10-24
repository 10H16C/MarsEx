"""Technology entity disambiguation.

Layout:
    resolver.py      the pipeline: normalize -> exact alias -> cache -> candidates -> LLM
    setup.py         build_resolver(): the one place components are created and wired
    steps/           each pipeline step (normalize, cache, candidates, llm)
    knowledge_base/  SQLite schema, seed import, and the in-memory snapshot
    tools/           command line, evaluation, and cache simulation
"""

from entity_resolver.config import Settings
from entity_resolver.domain import ResolverResult
from entity_resolver.resolver import Resolver
from entity_resolver.setup import build_resolver

__all__ = ["Resolver", "ResolverResult", "Settings", "build_resolver"]
