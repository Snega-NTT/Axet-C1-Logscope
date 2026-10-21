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
    from logscope.commands.timeline import TimelineResult

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


# ---------------------------------------------------------------------------
# Timeline formatter
# ---------------------------------------------------------------------------

_BAR_MAX_WIDTH = 30   # maximum number of '#' characters in the bar


def print_timeline(result: TimelineResult) -> None:
    """Print a human-readable error-count bar chart to stdout.

    Example output::

        ================================================
          LogScope — Timeline  (bucket: 15m)
        ================================================

        Bucket start          Errors  Chart
        2026-10-01 09:00:00        2  ####################
        2026-10-01 09:15:00        2  ####################
        2026-10-01 09:30:00        1  ##########

        Malformed lines       4

    The bar width is proportional to the error count relative to the bucket
    with the most errors.  A bucket with the maximum count gets a full
    ``_BAR_MAX_WIDTH``-character bar; zero-count buckets get an empty bar.
    """
    divider = "=" * 48

    print(divider)
    print(f"  LogScope \u2014 Timeline  (bucket: {result.bucket_minutes}m)")
    print(divider)
    print()

    if not result.buckets:
        print("  No ERROR entries found in the log file.")
        print()
        print(f"{'Malformed lines':<{_LABEL_WIDTH}}{result.malformed_lines}")
        print()
        return

    max_count = max(count for _, count in result.buckets)

    # Header
    print(f"{'Bucket start':<21}  {'Errors':>6}  Chart")

    for bucket_start, count in result.buckets:
        ts_str = bucket_start.strftime("%Y-%m-%d %H:%M:%S")
        if max_count > 0:
            bar_len = round((count / max_count) * _BAR_MAX_WIDTH)
        else:
            bar_len = 0
        bar = "#" * bar_len
        print(f"{ts_str}  {count:>6}  {bar}")

    print()
    print(f"{'Malformed lines':<{_LABEL_WIDTH}}{result.malformed_lines}")
    print()

