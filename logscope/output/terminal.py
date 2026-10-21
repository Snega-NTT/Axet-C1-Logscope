"""
logscope.output.terminal
~~~~~~~~~~~~~~~~~~~~~~~~
Human-readable terminal formatters for LogScope commands.

All output goes to stdout.
All errors and diagnostics must go to stderr (handled at the CLI layer).
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from logscope.commands.summary import SummaryResult

# Width of the left-hand label column for aligned output.
_LABEL_WIDTH = 22


def _fmt_ts(ts: datetime.datetime | None) -> str:
    """Format a datetime for display, or return a placeholder."""
    if ts is None:
        return "N/A"
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def print_summary(result: SummaryResult) -> None:
    """Print a human-readable summary to stdout.

    Example output::

        ╔══════════════════════════════════════════════╗
        ║            LogScope — Summary                ║
        ╚══════════════════════════════════════════════╝

        Log levels
          INFO                    8
          WARN                    3
          ERROR                   5

        Time range
          First entry             2026-10-01 09:00:12
          Last entry              2026-10-01 09:31:00

        Top 5 error messages
          1  (3)  Database connection refused
          2  (1)  Out of memory
          3  (1)  Scheduler timeout

        Malformed lines           2
    """
    divider = "=" * 48

    print(divider)
    print("  LogScope — Summary")
    print(divider)

    # --- Level counts ---
    print()
    print("Log levels")
    for level in ("INFO", "WARN", "ERROR"):
        count = result.levels.get(level, 0)
        label = f"  {level}"
        print(f"{label:<{_LABEL_WIDTH + 2}}{count}")

    # --- Time range ---
    print()
    print("Time range")
    first_label = "  First entry"
    last_label  = "  Last entry"
    print(f"{first_label:<{_LABEL_WIDTH + 2}}{_fmt_ts(result.first_timestamp)}")
    print(f"{last_label:<{_LABEL_WIDTH + 2}}{_fmt_ts(result.last_timestamp)}")

    # --- Top errors ---
    print()
    if result.top_errors:
        print("Top 5 error messages")
        for rank, (msg, count) in enumerate(result.top_errors, start=1):
            print(f"  {rank:<3}({count})  {msg}")
    else:
        print("Top 5 error messages      (none)")

    # --- Malformed lines ---
    print()
    label = "Malformed lines"
    print(f"{label:<{_LABEL_WIDTH}}{result.malformed_lines}")
    print()
