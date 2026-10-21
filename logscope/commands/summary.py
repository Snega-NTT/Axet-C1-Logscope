"""
logscope.commands.summary
~~~~~~~~~~~~~~~~~~~~~~~~~
Implements the ``logscope summary`` command.

Reads a log file one line at a time (streaming; never read() / readlines()),
accumulates bounded aggregate state, and returns a :class:`SummaryResult`
dataclass that callers can format however they like.

Aggregate state retained during a scan:
    - Three integer counters (INFO / WARN / ERROR).
    - One collections.Counter mapping error message → count.
    - Two datetime variables (running min and max of valid timestamps).
    - One integer malformed-line counter.

Memory is therefore O(unique ERROR messages), which is negligible in practice.
"""

from __future__ import annotations

import collections
import datetime
import pathlib
from dataclasses import dataclass, field
from typing import Optional

from logscope.parser import parse_line


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class SummaryResult:
    """All data produced by a summary scan of a log file.

    Attributes:
        levels:          Mapping of level name → count of valid entries.
        top_errors:      List of (message, count) tuples for the top-5 ERROR
                         messages ordered by descending count.
        first_timestamp: Minimum valid timestamp found, or None if no valid
                         entries exist.
        last_timestamp:  Maximum valid timestamp found, or None if no valid
                         entries exist.
        malformed_lines: Number of lines that parse_line returned None for.
    """

    levels: dict[str, int] = field(default_factory=lambda: {"INFO": 0, "WARN": 0, "ERROR": 0})
    top_errors: list[tuple[str, int]] = field(default_factory=list)
    first_timestamp: Optional[datetime.datetime] = None
    last_timestamp: Optional[datetime.datetime] = None
    malformed_lines: int = 0


# ---------------------------------------------------------------------------
# Core scan function
# ---------------------------------------------------------------------------


def run_summary(log_path: pathlib.Path) -> SummaryResult:
    """Stream *log_path* line-by-line and return a :class:`SummaryResult`.

    Args:
        log_path: Path to the log file to analyse.

    Returns:
        A populated :class:`SummaryResult`.  All fields are valid even when
        the file is empty or contains only malformed lines.

    Raises:
        OSError: If the file cannot be opened (e.g. does not exist or
                 permission denied).  The caller is responsible for turning
                 this into a user-facing error message.
    """
    levels: dict[str, int] = {"INFO": 0, "WARN": 0, "ERROR": 0}
    error_counter: collections.Counter[str] = collections.Counter()
    first_ts: Optional[datetime.datetime] = None
    last_ts: Optional[datetime.datetime] = None
    malformed: int = 0

    with log_path.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:                          # one line at a time — no read()
            entry = parse_line(raw)
            if entry is None:
                malformed += 1
                continue

            levels[entry.level] += 1

            if entry.level == "ERROR":
                error_counter[entry.message] += 1

            # Track true min/max — do NOT assume the file is ordered.
            if first_ts is None or entry.timestamp < first_ts:
                first_ts = entry.timestamp
            if last_ts is None or entry.timestamp > last_ts:
                last_ts = entry.timestamp

    top_errors: list[tuple[str, int]] = error_counter.most_common(5)

    return SummaryResult(
        levels=levels,
        top_errors=top_errors,
        first_timestamp=first_ts,
        last_timestamp=last_ts,
        malformed_lines=malformed,
    )
