"""Command line.

With no command, starts an interactive session that resolves names one at a time.
Commands: import the seed, resolve one name, evaluate a dataset, or simulate the cache.
"""

import argparse
import json
import sys
from collections.abc import Callable, Iterator
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError

from entity_resolver.config import Settings
from entity_resolver.errors import ResolverError, SeedValidationError
from entity_resolver.knowledge_base.importer import import_seed
from entity_resolver.setup import build_resolver
from entity_resolver.tools.cache_simulation import simulate
from entity_resolver.tools.evaluation.dataset import load_dataset
from entity_resolver.tools.evaluation.metrics import summarize
from entity_resolver.tools.evaluation.runner import run
from entity_resolver.tools.interactive import run_session

DEFAULT_DB = Path("var/kb.sqlite")
# Mean cost per Claude call measured on the dev set; see evaluate.md.
MEASURED_COST_PER_LLM_CALL = 0.0033


def main(argv: list[str] | None = None) -> int:
    """Run one CLI command, or the interactive session; return 0 on success, 1 on error."""
    # Variables already set in the environment take precedence over .env.
    load_dotenv()
    args = _parser().parse_args(argv)
    try:
        _COMMANDS[args.command or "interactive"](args)
    except (ResolverError, SeedValidationError, ValidationError, FileNotFoundError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


def _interactive(args: argparse.Namespace) -> None:
    resolver = build_resolver(args.db)
    print("Type a technology name to resolve it; 'exit' or Ctrl+C to quit.")
    print("Repeat a name (any casing or spacing) to see the cache answer it.\n")
    run_session(resolver, _prompted_lines(), print, MEASURED_COST_PER_LLM_CALL)


def _prompted_lines() -> Iterator[str]:
    while True:
        try:
            yield input("name> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return


def _import(args: argparse.Namespace) -> None:
    count = import_seed(args.seed, args.db)
    print(f"Imported {count} entities into {args.db}")


def _resolve(args: argparse.Namespace) -> None:
    print(json.dumps(build_resolver(args.db).resolve(args.name).to_dict(), indent=2))


def _evaluate(args: argparse.Namespace) -> None:
    settings = Settings()
    observations = run(
        load_dataset(args.dataset), lambda: build_resolver(args.db, settings), args.repeats
    )
    report = summarize(
        observations,
        settings,
        precision_target=args.precision_target,
        requests_per_day=args.requests_per_day,
        cache_hit_rate=args.cache_hit_rate,
    )
    print(json.dumps(asdict(report), indent=2))


def _simulate_cache(args: argparse.Namespace) -> None:
    report = simulate(
        args.db,
        Settings(),
        requests=args.requests,
        unique_names=args.unique_names,
        skew=args.skew,
        cache_sizes=args.cache_sizes,
        cost_per_llm_call=args.cost_per_llm_call,
        requests_per_day=args.requests_per_day,
        seed=args.seed,
    )
    print(json.dumps(asdict(report), indent=2))


_COMMANDS: dict[str, Callable[[argparse.Namespace], None]] = {
    "interactive": _interactive,
    "import": _import,
    "resolve": _resolve,
    "evaluate": _evaluate,
    "simulate-cache": _simulate_cache,
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="entity-resolver")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite knowledge base")
    commands = parser.add_subparsers(dest="command")

    import_command = commands.add_parser("import", help="validate and import seed JSON")
    import_command.add_argument("seed", type=Path)

    resolve_command = commands.add_parser("resolve", help="resolve one technology name")
    resolve_command.add_argument("name")

    evaluate_command = commands.add_parser("evaluate", help="run a labeled dataset (calls the LLM)")
    evaluate_command.add_argument("dataset", type=Path)
    evaluate_command.add_argument("--repeats", type=int, default=1)
    evaluate_command.add_argument("--precision-target", type=float, default=0.95)
    evaluate_command.add_argument("--requests-per-day", type=int, default=1_000_000)
    evaluate_command.add_argument("--cache-hit-rate", type=float, default=0.0)

    simulate_command = commands.add_parser(
        "simulate-cache", help="replay a synthetic request stream (no LLM calls, free)"
    )
    simulate_command.add_argument("--requests", type=int, default=50_000)
    simulate_command.add_argument("--unique-names", type=int, default=20_000)
    simulate_command.add_argument(
        "--skew", type=float, default=1.0, help="Zipf skew; higher means more repetition"
    )
    simulate_command.add_argument(
        "--cache-sizes",
        type=_int_list,
        default=[0, 100_000, 1_000_000, 10_000_000],
        help="comma-separated cache limits in bytes; the first is the baseline",
    )
    simulate_command.add_argument(
        "--cost-per-llm-call", type=float, default=MEASURED_COST_PER_LLM_CALL
    )
    simulate_command.add_argument("--requests-per-day", type=int, default=1_000_000)
    simulate_command.add_argument("--seed", type=int, default=7)
    return parser


def _int_list(text: str) -> list[int]:
    return [int(part) for part in text.split(",")]
