"""
logscope.cli
~~~~~~~~~~~~
Command-line entry point for LogScope.

Dispatch table:
    summary   →  logscope.commands.summary.run_summary
    timeline  →  logscope.commands.timeline.run_timeline
    grep      →  logscope.commands.grep.run_grep / iter_grep

Output formats supported by every command:
    (default)   human-readable terminal text
    --format json   valid JSON to stdout; nothing else on stdout
    --format md     Markdown report file written; path printed to stdout

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
    InvalidLevelError,
    InvalidSinceError,
    iter_grep,
    run_grep,
    validate_level,
    parse_since,
)
from logscope.commands.summary import run_summary
from logscope.commands.timeline import InvalidBucketError, parse_bucket, run_timeline
from logscope.output.json_fmt import (
    print_grep_json,
    print_summary_json,
    print_timeline_json,
)
from logscope.output.markdown import write_grep_md, write_summary_md, write_timeline_md
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
        help="Output format: json or md (default: terminal text).",
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
        help="Output format: json or md (default: terminal text).",
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
        help="Output format: json or md (default: terminal text).",
    )

    return parser


def _resolve_log_path(log_path: pathlib.Path) -> None:
    """Print an error to stderr and exit(1) if log_path is not a readable file."""
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
        elif args.fmt == "json":
            print_summary_json(result)
        elif args.fmt == "md":
            try:
                write_summary_md(result)
            except OSError as exc:
                print(f"logscope: error writing report: {exc}", file=sys.stderr)
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
        elif args.fmt == "json":
            print_timeline_json(result)
        elif args.fmt == "md":
            try:
                write_timeline_md(result)
            except OSError as exc:
                print(f"logscope: error writing report: {exc}", file=sys.stderr)
                sys.exit(1)

    # ------------------------------------------------------------------
    # grep
    # ------------------------------------------------------------------
    elif args.command == "grep":
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
            if args.fmt is None:
                result = run_grep(args.logfile, level_filter, since_filter)
                print_grep_footer(result)

            elif args.fmt == "json":
                print_grep_json(args.logfile, level_filter, since_filter)

            elif args.fmt == "md":
                # Collect entries for the Markdown table (bounded: only
                # matched entries, not the whole file).
                entries = []
                malformed_lines = 0
                match_count = 0
                for item in iter_grep(args.logfile, level_filter, since_filter):
                    if item is None:
                        malformed_lines += 1
                    else:
                        entries.append({
                            "timestamp": item.timestamp.isoformat(),
                            "level":     item.level,
                            "message":   item.message,
                            "raw":       item.raw,
                        })
                        match_count += 1

                from logscope.commands.grep import GrepResult
                result = GrepResult(
                    match_count=match_count,
                    malformed_lines=malformed_lines,
                    level_filter=level_filter,
                    since_filter=since_filter,
                )
                write_grep_md(result, entries)

        except OSError as exc:
            print(f"logscope: error: {exc}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
