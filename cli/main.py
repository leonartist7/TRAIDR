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

    news_parser = subparsers.add_parser("news", help="Fetch or score read-only news intelligence.")
    news_parser.add_argument("--fixture", action="store_true")
    news_parser.add_argument("--source", choices=("rss",))
    news_parser.add_argument("--url")

    macro_parser = subparsers.add_parser("macro", help="Fetch or score read-only macro intelligence.")
    macro_parser.add_argument("--fixture", action="store_true")

    watch_parser = subparsers.add_parser("watch", help="Manage the local read-only watchlist.")
    watch_subparsers = watch_parser.add_subparsers(dest="watch_command", required=True)
    watch_add_parser = watch_subparsers.add_parser("add", help="Add or reactivate a watched pair.")
    watch_add_parser.add_argument("pair_ref")
    watch_add_parser.add_argument("--note", default="")
    watch_add_parser.add_argument("--tag", action="append", default=[])
    watch_subparsers.add_parser("list", help="List active watched pairs.")
    watch_remove_parser = watch_subparsers.add_parser("remove", help="Deactivate a watched pair.")
    watch_remove_parser.add_argument("pair_ref")
    watch_subparsers.add_parser("scan", help="Scan active watched pairs in read-only mode.")

    report_parser = subparsers.add_parser("report", help="Show research summaries.")
    report_parser.add_argument("--type", choices=("4h", "daily"), default="daily")
    report_parser.add_argument("--limit", type=int, default=5)

    alerts_parser = subparsers.add_parser("alerts", help="Show local alert history.")
    alerts_parser.add_argument("--limit", type=int, default=10)
    alert_subparsers = alerts_parser.add_subparsers(dest="alert_command")
    alert_subparsers.add_parser("test", help="Run fixture alert rules and store local alert history.")
    alert_subparsers.add_parser("rules", help="List configured research alert rules.")

    portfolio_parser = subparsers.add_parser("portfolio", help="Manage manual local portfolio analysis entries.")
    portfolio_subparsers = portfolio_parser.add_subparsers(dest="portfolio_command", required=True)
    portfolio_add_parser = portfolio_subparsers.add_parser("add", help="Add a manual portfolio entry.")
    portfolio_add_parser.add_argument("symbol")
    portfolio_add_parser.add_argument("--entry", required=True, type=_decimal_arg, dest="entry_price")
    portfolio_add_parser.add_argument("--size-usd", required=True, type=_decimal_arg)
    portfolio_add_parser.add_argument("--thesis", required=True)
    portfolio_add_parser.add_argument("--chain", default="unknown")
    portfolio_add_parser.add_argument("--pair-ref")
    portfolio_add_parser.add_argument("--stop-zone", default="")
    portfolio_add_parser.add_argument("--take-profit-zone", default="")
    portfolio_add_parser.add_argument("--conviction", default="medium")
    portfolio_add_parser.add_argument("--risk-level", default="unknown")
    portfolio_add_parser.add_argument("--notes", default="")
    portfolio_subparsers.add_parser("list", help="List active manual portfolio entries.")
    portfolio_remove_parser = portfolio_subparsers.add_parser("remove", help="Deactivate a manual portfolio entry.")
    portfolio_remove_parser.add_argument("entry_id")
    portfolio_subparsers.add_parser("report", help="Show manual portfolio exposure report.")
    portfolio_subparsers.add_parser("monitor", help="Monitor manual positions against local sell-risk evidence.")
    portfolio_subparsers.add_parser("sell-risk", help="Show manual position sell-risk decisions.")

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
    elif args.command == "news":
        result = commands.news(fixture=args.fixture, source=args.source, url=args.url)
    elif args.command == "macro":
        result = commands.macro(fixture=args.fixture)
    elif args.command == "watch":
        if args.watch_command == "add":
            result = commands.watch_add(
                args.pair_ref,
                database=args.database,
                note=args.note,
                tags=tuple(args.tag),
            )
        elif args.watch_command == "list":
            result = commands.watch_list(database=args.database)
        elif args.watch_command == "remove":
            result = commands.watch_remove(args.pair_ref, database=args.database)
        elif args.watch_command == "scan":
            result = commands.watch_scan(database=args.database)
        else:  # pragma: no cover - argparse prevents this branch
            raise AssertionError(f"unsupported watch command: {args.watch_command}")
    elif args.command == "report":
        result = commands.report(args.database, report_type=args.type, limit=args.limit)
    elif args.command == "alerts":
        if args.alert_command == "test":
            result = commands.alerts_test(args.database)
        elif args.alert_command == "rules":
            result = commands.alerts_rules()
        else:
            result = commands.alerts(args.database, limit=args.limit)
    elif args.command == "portfolio":
        if args.portfolio_command == "add":
            result = commands.portfolio_add(
                args.symbol,
                database=args.database,
                entry_price=args.entry_price,
                size_usd=args.size_usd,
                thesis=args.thesis,
                chain=args.chain,
                pair_ref=args.pair_ref,
                stop_zone=args.stop_zone,
                take_profit_zone=args.take_profit_zone,
                conviction=args.conviction,
                risk_level=args.risk_level,
                notes=args.notes,
            )
        elif args.portfolio_command == "list":
            result = commands.portfolio_list(database=args.database)
        elif args.portfolio_command == "remove":
            result = commands.portfolio_remove(args.entry_id, database=args.database)
        elif args.portfolio_command == "report":
            result = commands.portfolio_report(database=args.database)
        elif args.portfolio_command == "monitor":
            result = commands.portfolio_monitor(database=args.database)
        elif args.portfolio_command == "sell-risk":
            result = commands.portfolio_monitor(database=args.database)
        else:  # pragma: no cover - argparse prevents this branch
            raise AssertionError(f"unsupported portfolio command: {args.portfolio_command}")
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


def _decimal_arg(value: str):
    from decimal import Decimal

    return Decimal(value)


if __name__ == "__main__":
    raise SystemExit(main())
