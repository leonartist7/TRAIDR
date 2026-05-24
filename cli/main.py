"""Argparse entry point for the TRAIDR operator command center."""

from __future__ import annotations

import argparse

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

    report_parser = subparsers.add_parser("report", help="Show research summaries.")
    report_parser.add_argument("--type", choices=("4h", "daily"), default="daily")
    report_parser.add_argument("--limit", type=int, default=5)

    alerts_parser = subparsers.add_parser("alerts", help="Show local alert history.")
    alerts_parser.add_argument("--limit", type=int, default=10)

    subparsers.add_parser("dashboard", help="Print the safe Streamlit dashboard launch command.")
    subparsers.add_parser("scheduler-once", help="Run due local research scheduler tasks once.")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "status":
        result = commands.status(args.database)
    elif args.command == "simulate":
        result = commands.simulate(args.database, memory=args.memory)
    elif args.command == "inspect":
        result = commands.inspect(args.database, limit=args.limit)
    elif args.command == "radar":
        result = commands.radar(args.database, fixture=args.fixture, limit=args.limit)
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


if __name__ == "__main__":
    raise SystemExit(main())
