from entity_resolver.domain import Selection
from entity_resolver.errors import SelectorError
from entity_resolver.resolver import Resolver
from entity_resolver.tools.interactive import run_session
from tests.fakes import FakeSelector


def _run(resolver: Resolver, lines: list[str]) -> tuple[list[str], int, int, int, int]:
    output: list[str] = []
    stats = run_session(resolver, lines, output.append, cost_per_llm_call=0.01)
    return output, stats.exact, stats.cache_hits, stats.llm_calls, stats.errors


def test_repeated_name_is_answered_from_cache(resolver: Resolver, selector: FakeSelector) -> None:
    selector.responses["Microsoft sp"] = Selection("ms_sharepoint", 0.9)
    output, _, cache_hits, llm_calls, _ = _run(resolver, ["Microsoft sp", "MICROSOFT  sp"])
    assert (cache_hits, llm_calls, len(selector.calls)) == (1, 1, 1)
    assert "llm: score 0.90" in output[0]
    assert "cache" in output[1]
    assert "cache hits saved up to $0.0100" in output[-1]


def test_exact_alias_skips_llm(resolver: Resolver, selector: FakeSelector) -> None:
    output, exact, _, llm_calls, _ = _run(resolver, ["AWS"])
    assert (exact, llm_calls, selector.calls) == (1, 0, [])
    assert "Amazon Web Services" in output[0]


def test_low_score_is_shown_as_below_threshold(resolver: Resolver, selector: FakeSelector) -> None:
    selector.responses["Microsoft sp"] = Selection("ms_sharepoint", 0.5)
    output, *_ = _run(resolver, ["Microsoft sp"])
    assert "unknown" in output[0]
    assert "Microsoft SharePoint at 0.50, below threshold" in output[0]


def test_error_is_reported_and_session_continues(
    resolver: Resolver, selector: FakeSelector
) -> None:
    selector.error = SelectorError("timeout")
    output, exact, _, _, errors = _run(resolver, ["Sentinel", "AWS"])
    assert (errors, exact) == (1, 1)
    assert output[0] == "  error: timeout"


def test_exit_stops_and_blank_lines_are_skipped(resolver: Resolver) -> None:
    output, exact, *_ = _run(resolver, ["", "AWS", "exit", "AWS EKS"])
    assert exact == 1
    assert output[-2].startswith("1 requests")
