"""Command line: import the seed, resolve a name, or evaluate a labeled dataset."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from pydantic import ValidationError

from entity_resolver.composition import build_resolver
from entity_resolver.config import Settings
from entity_resolver.errors import ResolverError, SeedValidationError
from entity_resolver.evaluation.dataset import load_dataset
from entity_resolver.evaluation.metrics import summarize
from entity_resolver.evaluation.runner import run
from entity_resolver.store.importer import import_seed

DEFAULT_DB = Path("var/kb.sqlite")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "import":
            count = import_seed(args.seed, args.db)
            print(f"Imported {count} entities into {args.db}")
        elif args.command == "resolve":
            print(json.dumps(build_resolver(args.db).resolve(args.name).to_dict(), indent=2))
        else:
            _evaluate(args)
    except (ResolverError, SeedValidationError, ValidationError, FileNotFoundError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="entity-resolver")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite knowledge base")
    commands = parser.add_subparsers(dest="command", required=True)

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
    return parser


if __name__ == "__main__":
    sys.exit(main())
