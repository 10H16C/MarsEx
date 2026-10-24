"""Claude adapter for candidate selection using structured output."""

from collections.abc import Sequence
from functools import cached_property

from anthropic import Anthropic, AnthropicError, omit
from pydantic import BaseModel

from entity_resolver.config import Settings
from entity_resolver.domain import Candidate, Selection
from entity_resolver.errors import InvalidSelectionError, SelectorError
from entity_resolver.steps.llm.prompt import REQUEST_FORMAT_VERSION, SYSTEM_PROMPT, render_request
from entity_resolver.versioning import fingerprint

# Thinking is always on for this model family, so leave room beyond the small JSON answer.
_MAX_TOKENS = 4096
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class _LlmSelection(BaseModel):
    candidate_id: str | None
    match_score: float


class AnthropicSelector:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.version = fingerprint(
            settings.model,
            settings.effort,
            settings.use_refusal_fallback,
            SYSTEM_PROMPT,
            REQUEST_FORMAT_VERSION,
        )

    @cached_property
    def _client(self) -> Anthropic:
        # Created on first use so exact matches and cache hits work without credentials.
        return Anthropic()

    def select(self, query: str, candidates: Sequence[Candidate]) -> Selection:
        settings = self._settings
        try:
            response = self._client.beta.messages.parse(
                model=settings.model,
                max_tokens=_MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": render_request(query, candidates)}],
                output_format=_LlmSelection,
                output_config={"effort": settings.effort},
                fallbacks="default" if settings.use_refusal_fallback else omit,
                betas=[_FALLBACK_BETA] if settings.use_refusal_fallback else omit,
            )
        except AnthropicError as error:
            raise SelectorError(f"LLM request failed: {error}") from error
        except ValueError as error:
            raise InvalidSelectionError(f"LLM output did not match the schema: {error}") from error

        parsed = response.parsed_output
        if parsed is None:
            raise InvalidSelectionError(
                f"No structured output (stop_reason={response.stop_reason})"
            )
        # PRODUCTION: export token usage and stop reasons to monitoring.
        return Selection(
            candidate_id=parsed.candidate_id,
            match_score=parsed.match_score,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
