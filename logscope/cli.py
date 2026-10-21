"""
logscope.cli
~~~~~~~~~~~~
Command-line entry point for LogScope.

Dispatch table:
    summary   →  logscope.commands.summary.run_summary
    timeline  →  logscope.commands.timeline.run_timeline
    grep      →  logscope.commands.grep.run_grep

Usage:
    python -m logscope summary  <logfile> [--format json|md]
    python -m logscope timeline <logfile> --bucket <duration> [--format json|md]
    python -m logscope grep     <logfile> [--level LEVEL] [--since TIMESTAMP]
                                          [--format json|md]
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from logscope.commands.grep import (
    GrepResult,
    InvalidLevelError,
    InvalidSinceError,
    run_grep,
    validate_level,
    parse_since,
)
from logscope.commands.summary import run_summary
from logscope.commands.timeline import InvalidBucketError, parse_bucket, run_timeline
from logscope.output.terminal import print_grep_footer, print_summary, print_timeline


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="logscope",
        description="Analyse application log files from the command line.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="command")
    subparsers.required = True

    # ------------------------------------------------------------------
    # summary
    # ------------------------------------------------------------------
    summary_p = subparsers.add_parser("summary", help="Show log-level counts and top errors.")
    summary_p.add_argument("logfile", type=pathlib.Path, help="Path to the log file.")
    summary_p.add_argument(
        "--format",
        dest="fmt",
        choices=["json", "md"],
        default=None,
        help="Output format (default: terminal text).",
    )

    # ------------------------------------------------------------------
    # timeline
    # ------------------------------------------------------------------
    timeline_p = subparsers.add_parser(
        "timeline",
        help="Show ERROR counts per time bucket as a bar chart.",
    )
    timeline_p.add_argument("logfile", type=pathlib.Path, help="Path to the log file.")
    timeline_p.add_argument(
        "--bucket",
        dest="bucket",
        required=True,
        metavar="DURATION",
        help="Bucket width, e.g. 1m, 5m, 15m, 60m.  Required.",
    )
    timeline_p.add_argument(
        "--format",
        dest="fmt",
        choices=["json", "md"],
        default=None,
        help="Output format (default: terminal text).",
    )

    # ------------------------------------------------------------------
    # grep
    # ------------------------------------------------------------------
    grep_p = subparsers.add_parser(
        "grep",
        help="Filter log entries by level and/or timestamp.",
    )
    grep_p.add_argument("logfile", type=pathlib.Path, help="Path to the log file.")
    grep_p.add_argument(
        "--level",
        dest="level",
        default=None,
        metavar="LEVEL",
        help="Filter by level: INFO, WARN, or ERROR.",
    )
    grep_p.add_argument(
        "--since",
        dest="since",
        default=None,
        metavar="TIMESTAMP",
        help='Include entries at or after this time.  Format: "YYYY-MM-DD HH:MM".',
    )
    grep_p.add_argument(
        "--format",
        dest="fmt",
        choices=["json", "md"],
        default=None,
        help="Output format (default: terminal text).",
    )

    return parser


def _resolve_log_path(log_path: pathlib.Path) -> None:
    """Print an error and exit(1) if log_path is not a readable file."""
    if not log_path.exists():
        print(f"logscope: error: file not found: {log_path}", file=sys.stderr)
        sys.exit(1)
    if not log_path.is_file():
        print(f"logscope: error: not a file: {log_path}", file=sys.stderr)
        sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    """Entry point; exits with a non-zero code on any error."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    # ------------------------------------------------------------------
    # summary
    # ------------------------------------------------------------------
    if args.command == "summary":
        _resolve_log_path(args.logfile)
        try:
            result = run_summary(args.logfile)
        except OSError as exc:
            print(f"logscope: error: {exc}", file=sys.stderr)
            sys.exit(1)

        if args.fmt is None:
            print_summary(result)
        else:
            print(f"logscope: --format {args.fmt} not yet implemented", file=sys.stderr)
            sys.exit(1)

    # ------------------------------------------------------------------
    # timeline
    # ------------------------------------------------------------------
    elif args.command == "timeline":
        try:
            bucket_minutes = parse_bucket(args.bucket)
        except InvalidBucketError as exc:
            print(f"logscope: error: {exc}", file=sys.stderr)
            sys.exit(1)

        _resolve_log_path(args.logfile)

        try:
            result = run_timeline(args.logfile, bucket_minutes)
        except OSError as exc:
            print(f"logscope: error: {exc}", file=sys.stderr)
            sys.exit(1)

        if args.fmt is None:
            print_timeline(result)
        else:
            print(f"logscope: --format {args.fmt} not yet implemented", file=sys.stderr)
            sys.exit(1)

    # ------------------------------------------------------------------
    # grep
    # ------------------------------------------------------------------
    elif args.command == "grep":
        # Validate filters before touching the file.
        level_filter = None
        since_filter = None

        if args.level is not None:
            try:
                level_filter = validate_level(args.level)
            except InvalidLevelError as exc:
                print(f"logscope: error: {exc}", file=sys.stderr)
                sys.exit(1)

        if args.since is not None:
            try:
                since_filter = parse_since(args.since)
            except InvalidSinceError as exc:
                print(f"logscope: error: {exc}", file=sys.stderr)
                sys.exit(1)

        _resolve_log_path(args.logfile)

        try:
            result = run_grep(args.logfile, level_filter, since_filter)
        except OSError as exc:
            print(f"logscope: error: {exc}", file=sys.stderr)
            sys.exit(1)

        if args.fmt is None:
            print_grep_footer(result)
        else:
            print(f"logscope: --format {args.fmt} not yet implemented", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
