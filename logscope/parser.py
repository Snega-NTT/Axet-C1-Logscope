"""
logscope.parser
~~~~~~~~~~~~~~~
Streaming log-line parser for LogScope.

Supported log format:
    YYYY-MM-DD HH:MM:SS LEVEL message

    - YYYY-MM-DD  date
    - HH:MM:SS    time (24-hour)
    - LEVEL       one of INFO, WARN, ERROR  (case-sensitive)
    - message     one or more non-whitespace characters (rest of line)

Any line that does not conform to this format is considered malformed.
Malformed lines are never raised as exceptions; callers receive None.

Usage example (streaming a file without reading it fully into memory):

    from logscope.parser import parse_line, LogEntry

    with open("app.log", "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            entry = parse_line(raw)
            if entry is None:
                malformed_count += 1
            else:
                process(entry)
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_LEVELS: frozenset[str] = frozenset({"INFO", "WARN", "ERROR"})

# Matches the canonical log format.  Each named group corresponds to a field
# in LogEntry.  \s+ between fields tolerates one or more whitespace chars,
# which handles tab-separated variants and double-spaced logs.
_LOG_RE: re.Pattern[str] = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})"
    r"\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2})"
    r"\s+"
    r"(?P<level>[A-Z]+)"
    r"\s+"
    r"(?P<message>\S.*)"
    r"$"
)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LogEntry:
    """A single successfully parsed log line.

    Attributes:
        timestamp:  Parsed datetime in UTC-naive form (as written in the log).
        level:      One of "INFO", "WARN", "ERROR".
        message:    The message text (stripped of leading/trailing whitespace).
        raw:        The original line with only the trailing newline stripped.
                    Preserved so that ``grep`` output matches the source file.
    """

    timestamp: datetime.datetime
    level: str
    message: str
    raw: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_line(raw: str) -> LogEntry | None:
    """Parse one log line and return a :class:`LogEntry`, or ``None`` if malformed.

    A line is considered malformed when any of the following is true:

    * The line is empty or contains only whitespace.
    * The line does not match the expected ``YYYY-MM-DD HH:MM:SS LEVEL message``
      pattern.
    * The level token is not one of ``INFO``, ``WARN``, or ``ERROR``.
    * The date/time portion cannot be converted to a valid
      :class:`datetime.datetime` (e.g. month 13, day 32).
    * The message portion is absent or contains only whitespace.

    This function never raises an exception regardless of input.

    Args:
        raw: A single line of text, possibly including a trailing newline.

    Returns:
        A :class:`LogEntry` on success, or ``None`` for malformed lines.
    """
    # Strip only the trailing newline/carriage-return so that raw is preserved
    # faithfully for grep output while still matching the regex cleanly.
    stripped = raw.rstrip("\r\n")

    if not stripped.strip():
        return None

    match = _LOG_RE.match(stripped)
    if match is None:
        return None

    level = match.group("level")
    if level not in SUPPORTED_LEVELS:
        return None

    message = match.group("message").strip()
    if not message:
        return None

    # Parse timestamp directly from captured groups to avoid the overhead of
    # datetime.strptime (which is ~10× slower than direct integer conversion
    # for 2M+ lines and is the dominant bottleneck on large files).
    try:
        date_str = match.group("date")   # "YYYY-MM-DD"
        time_str = match.group("time")   # "HH:MM:SS"
        timestamp = datetime.datetime(
            int(date_str[0:4]),   # year
            int(date_str[5:7]),   # month
            int(date_str[8:10]),  # day
            int(time_str[0:2]),   # hour
            int(time_str[3:5]),   # minute
            int(time_str[6:8]),   # second
        )
    except ValueError:
        return None

    return LogEntry(
        timestamp=timestamp,
        level=level,
        message=message,
        raw=stripped,
    )
