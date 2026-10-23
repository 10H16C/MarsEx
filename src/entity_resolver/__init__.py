"""Technology entity disambiguation."""

from entity_resolver.composition import build_resolver
from entity_resolver.config import Settings
from entity_resolver.models import ResolverResult
from entity_resolver.resolver import Resolver

__all__ = ["Resolver", "ResolverResult", "Settings", "build_resolver"]
