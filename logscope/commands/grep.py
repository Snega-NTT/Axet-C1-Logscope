"""
logscope.commands.grep
~~~~~~~~~~~~~~~~~~~~~~
Implements the ``logscope grep`` command.

Reads a log file one line at a time (streaming; never read() / readlines()).
Entries are written to stdout as they are matched — no in-memory accumulation
of the result set.  Only the running match count and malformed-line count are
retained in memory (O(1)).

Filter semantics
----------------
* ``--level``  — exact match on entry.level (INFO / WARN / ERROR).
* ``--since``  — inclusive: entry.timestamp >= since_dt.
* Both filters may be combined (AND logic).
* If neither filter is supplied, every valid entry is printed.

``--since`` accepts minute-precision input ("YYYY-MM-DD HH:MM") and is
compared against the full seconds-precision entry timestamp; seconds are
treated as 00 on the since side (i.e. ``09:00`` matches ``09:00:00`` and
later).

Streaming JSON note
-------------------
JSON output is not implemented in this step.  When it is added it will be
written incrementally (open-brace → entries one-by-one → close-brace) so the
full entry list is never collected in memory, honouring the spec requirement.
"""

from __future__ import annotations

import datetime
import pathlib
import re
from dataclasses import dataclass
from typing import Generator, Optional

from logscope.parser import LogEntry, parse_line

# ---------------------------------------------------------------------------
# --since parsing
# ---------------------------------------------------------------------------

# Accepts "YYYY-MM-DD HH:MM" (required) or "YYYY-MM-DD HH:MM:SS" (optional).
_SINCE_FORMATS = ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S")


class InvalidSinceError(ValueError):
    """Raised when the --since argument cannot be parsed."""


class InvalidLevelError(ValueError):
    """Raised when the --level argument is not a supported log level."""


SUPPORTED_LEVELS = frozenset({"INFO", "WARN", "ERROR"})


def parse_since(raw: str) -> datetime.datetime:
    """Parse a ``--since`` value and return a :class:`datetime.datetime`.

    Args:
        raw: The raw CLI value, e.g. ``"2026-10-01 09:00"`` or
             ``"2026-10-01 09:00:30"``.

    Returns:
        A :class:`datetime.datetime` at second precision (seconds default to 0
        when only minutes are supplied).

    Raises:
        :class:`InvalidSinceError`: If the string cannot be parsed in any
            accepted format.
    """
    raw = raw.strip()
    for fmt in _SINCE_FORMATS:
        try:
            return datetime.datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise InvalidSinceError(
        f"invalid --since value {raw!r}: expected format "
        f"\"YYYY-MM-DD HH:MM\" or \"YYYY-MM-DD HH:MM:SS\""
    )


def validate_level(raw: str) -> str:
    """Return *raw* uppercased if it is a supported level, else raise.

    Raises:
        :class:`InvalidLevelError`: If the value is not in
            ``{INFO, WARN, ERROR}``.
    """
    upper = raw.strip().upper()
    if upper not in SUPPORTED_LEVELS:
        raise InvalidLevelError(
            f"invalid --level value {raw!r}: must be one of "
            f"INFO, WARN, ERROR"
        )
    return upper


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class GrepResult:
    """Summary counters returned after a grep scan.

    The matched entries themselves are streamed to stdout during the scan;
    only the counts are collected here.

    Attributes:
        match_count:     Number of entries that passed all filters.
        malformed_lines: Number of lines parse_line returned None for.
        level_filter:    The ``--level`` value used, or None.
        since_filter:    The ``--since`` datetime used, or None.
    """

    match_count: int = 0
    malformed_lines: int = 0
    level_filter: Optional[str] = None
    since_filter: Optional[datetime.datetime] = None


# ---------------------------------------------------------------------------
# Core streaming function
# ---------------------------------------------------------------------------


def iter_grep(
    log_path: pathlib.Path,
    level_filter: Optional[str] = None,
    since_filter: Optional[datetime.datetime] = None,
) -> Generator[LogEntry | None, None, None]:
    """Yield matching :class:`LogEntry` objects one at a time, or ``None`` for
    each malformed line.

    Callers iterate this generator to stream results without ever holding the
    full match set in memory.

    Args:
        log_path:      Path to the log file.
        level_filter:  If set, only entries whose level equals this value are
                       yielded.
        since_filter:  If set, only entries whose timestamp >= this value are
                       yielded.

    Yields:
        :class:`LogEntry` for each matching valid line.
        ``None`` for each malformed line (so the caller can count them).

    Raises:
        OSError: If the file cannot be opened.
    """
    with log_path.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:                          # one line at a time — no read()
            entry = parse_line(raw)
            if entry is None:
                yield None                      # caller counts malformed
                continue

            if level_filter is not None and entry.level != level_filter:
                continue
            if since_filter is not None and entry.timestamp < since_filter:
                continue

            yield entry


def run_grep(
    log_path: pathlib.Path,
    level_filter: Optional[str] = None,
    since_filter: Optional[datetime.datetime] = None,
) -> GrepResult:
    """Stream *log_path*, print matching lines to stdout, return counters.

    Each matching entry is printed immediately via ``print(entry.raw)`` so the
    full result list is never held in memory.

    Args:
        log_path:      Path to the log file.
        level_filter:  Optional level string (INFO / WARN / ERROR).
        since_filter:  Optional inclusive lower-bound datetime.

    Returns:
        A :class:`GrepResult` with match and malformed counts.

    Raises:
        OSError: If the file cannot be opened.
    """
    match_count = 0
    malformed_lines = 0

    for item in iter_grep(log_path, level_filter, since_filter):
        if item is None:
            malformed_lines += 1
        else:
            print(item.raw)
            match_count += 1

    return GrepResult(
        match_count=match_count,
        malformed_lines=malformed_lines,
        level_filter=level_filter,
        since_filter=since_filter,
    )
