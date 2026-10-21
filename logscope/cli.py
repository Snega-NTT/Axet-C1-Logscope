"""
logscope.cli
~~~~~~~~~~~~
Command-line entry point for LogScope.

Dispatch table (grows as commands are added):
    summary   →  logscope.commands.summary.run_summary

Usage:
    python -m logscope summary <logfile> [--format json|md]
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from logscope.commands.summary import run_summary
from logscope.output.terminal import print_summary


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

    return parser


def main(argv: list[str] | None = None) -> None:
    """Entry point; exits with a non-zero code on any error."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "summary":
        log_path: pathlib.Path = args.logfile
        if not log_path.exists():
            print(f"logscope: error: file not found: {log_path}", file=sys.stderr)
            sys.exit(1)
        if not log_path.is_file():
            print(f"logscope: error: not a file: {log_path}", file=sys.stderr)
            sys.exit(1)

        try:
            result = run_summary(log_path)
        except OSError as exc:
            print(f"logscope: error: {exc}", file=sys.stderr)
            sys.exit(1)

        if args.fmt is None:
            print_summary(result)
        else:
            # JSON and Markdown output will be wired in a later step.
            print(
                f"logscope: --format {args.fmt} not yet implemented",
                file=sys.stderr,
            )
            sys.exit(1)


if __name__ == "__main__":
    main()
