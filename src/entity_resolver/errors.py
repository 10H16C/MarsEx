"""Errors raised by the resolver and the importer."""


class ResolverError(Exception):
    """A resolution could not be completed; this is not evidence that the product is unknown."""


class SelectorError(ResolverError):
    """The LLM provider request failed."""


class InvalidSelectionError(ResolverError):
    """The LLM returned output that violates the selection contract."""


class SeedValidationError(ValueError):
    """The seed data breaks a knowledge-base rule."""
