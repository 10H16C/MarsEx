from types import SimpleNamespace

import pytest

from entity_resolver.config import Settings
from entity_resolver.errors import SelectorError
from entity_resolver.steps.llm.claude import AnthropicSelector


def _selector_whose_client_raises(error: Exception) -> AnthropicSelector:
    def parse(**_: object) -> None:
        raise error

    selector = AnthropicSelector(Settings())
    # Replace the lazily created SDK client so no request is made.
    selector.__dict__["_client"] = SimpleNamespace(
        beta=SimpleNamespace(messages=SimpleNamespace(parse=parse))
    )
    return selector


def test_missing_credentials_become_selector_error() -> None:
    selector = _selector_whose_client_raises(
        TypeError('"Could not resolve authentication method. Expected one of api_key, ..."')
    )
    with pytest.raises(SelectorError, match="ANTHROPIC_API_KEY"):
        selector.select("Microsoft sp", [])


def test_other_type_errors_are_not_hidden() -> None:
    selector = _selector_whose_client_raises(TypeError("unexpected keyword argument"))
    with pytest.raises(TypeError, match="unexpected keyword"):
        selector.select("Microsoft sp", [])
