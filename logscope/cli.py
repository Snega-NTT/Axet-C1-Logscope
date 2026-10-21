"""
logscope.cli
~~~~~~~~~~~~
Command-line entry point for LogScope.

Dispatch table:
    summary   →  logscope.commands.summary.run_summary
    timeline  →  logscope.commands.timeline.run_timeline

Usage:
    python -m logscope summary  <logfile> [--format json|md]
    python -m logscope timeline <logfile> --bucket <duration> [--format json|md]
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from logscope.commands.summary import run_summary
from logscope.commands.timeline import InvalidBucketError, parse_bucket, run_timeline
from logscope.output.terminal import print_summary, print_timeline


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
            # JSON and Markdown output wired in a later step.
            print(f"logscope: --format {args.fmt} not yet implemented", file=sys.stderr)
            sys.exit(1)

    # ------------------------------------------------------------------
    # timeline
    # ------------------------------------------------------------------
    elif args.command == "timeline":
        # Validate bucket before touching the file.
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


if __name__ == "__main__":
    main()

