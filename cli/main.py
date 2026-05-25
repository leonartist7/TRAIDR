"""Argparse entry point for the TRAIDR operator command center."""

from __future__ import annotations

import argparse
import sys

from cli import commands


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="traidr", description="TRAIDR local operator command center.")
    parser.add_argument("--database", help="DuckDB path override for commands that read or write local storage.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show local runtime and storage status.")

    simulate_parser = subparsers.add_parser("simulate", help="Run the deterministic paper simulation.")
    simulate_parser.add_argument("--memory", action="store_true", help="Use in-memory DuckDB instead of local DB.")

    inspect_parser = subparsers.add_parser("inspect", help="Show tables and latest local records.")
    inspect_parser.add_argument("--limit", type=int, default=5)

    radar_parser = subparsers.add_parser("radar", help="Show opportunity radar output.")
    radar_parser.add_argument("--fixture", action="store_true", help="Use fixture radar output even if DB is empty.")
    radar_parser.add_argument("--limit", type=int, default=10)

    scan_parser = subparsers.add_parser("scan", help="Run read-only market scan research.")
    scan_parser.add_argument("--fixture", action="store_true", help="Use deterministic offline scan fixtures.")
    scan_parser.add_argument("--source", choices=("dexscreener",), help="Optional real read-only market source.")
    scan_parser.add_argument("--pair-ref", action="append", default=[], help="Pair reference for optional real-source scan.")
    scan_parser.add_argument("--limit", type=int, default=10)

    discover_parser = subparsers.add_parser("discover", help="Discover read-only token candidates.")
    discover_parser.add_argument("--fixture", action="store_true", help="Use deterministic offline discovery fixtures.")
    discover_parser.add_argument("--source", choices=("dexscreener",), help="Optional real read-only discovery source.")
    discover_parser.add_argument("--limit", type=int, default=20)

    token_parser = subparsers.add_parser("token", help="Show a read-only token detail intelligence card.")
    token_parser.add_argument("--fixture", action="store_true", help="Use deterministic offline token detail fixture.")
    token_parser.add_argument("--pair-ref", help="Pair reference for optional real-source token detail.")
    token_parser.add_argument("--source", choices=("dexscreener",), help="Optional real read-only token detail source.")

    subparsers.add_parser("briefing", help="Generate a read-only daily intelligence briefing from DuckDB.")

    report_parser = subparsers.add_parser("report", help="Show research summaries.")
    report_parser.add_argument("--type", choices=("4h", "daily"), default="daily")
    report_parser.add_argument("--limit", type=int, default=5)

    alerts_parser = subparsers.add_parser("alerts", help="Show local alert history.")
    alerts_parser.add_argument("--limit", type=int, default=10)

    subparsers.add_parser("dashboard", help="Print the safe Streamlit dashboard launch command.")
    subparsers.add_parser("scheduler-once", help="Run due local research scheduler tasks once.")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(_normalize_global_database_arg(argv))
    if args.command == "status":
        result = commands.status(args.database)
    elif args.command == "simulate":
        result = commands.simulate(args.database, memory=args.memory)
    elif args.command == "inspect":
        result = commands.inspect(args.database, limit=args.limit)
    elif args.command == "radar":
        result = commands.radar(args.database, fixture=args.fixture, limit=args.limit)
    elif args.command == "scan":
        result = commands.scan(
            args.database,
            fixture=args.fixture,
            source=args.source,
            pair_refs=tuple(args.pair_ref),
            limit=args.limit,
        )
    elif args.command == "discover":
        result = commands.discover(
            args.database,
            fixture=args.fixture,
            source=args.source,
            limit=args.limit,
        )
    elif args.command == "token":
        result = commands.token_detail(
            args.database,
            fixture=args.fixture,
            pair_ref=args.pair_ref,
            source=args.source,
        )
    elif args.command == "briefing":
        result = commands.briefing(args.database)
    elif args.command == "report":
        result = commands.report(args.database, report_type=args.type, limit=args.limit)
    elif args.command == "alerts":
        result = commands.alerts(args.database, limit=args.limit)
    elif args.command == "dashboard":
        result = commands.dashboard(args.database)
    elif args.command == "scheduler-once":
        result = commands.scheduler_once(args.database)
    else:  # pragma: no cover - argparse prevents this branch
        raise AssertionError(f"unsupported command: {args.command}")
    print(result.output)
    return result.exit_code


def _normalize_global_database_arg(argv: list[str] | None) -> list[str] | None:
    """Accept --database before or after the subcommand for operator ergonomics."""

    args = list(sys.argv[1:] if argv is None else argv)
    if "--database" not in args:
        return args
    index = args.index("--database")
    if index == 0:
        return args
    if index + 1 >= len(args):
        return args
    value = args[index + 1]
    del args[index : index + 2]
    return ["--database", value, *args]


if __name__ == "__main__":
    raise SystemExit(main())
