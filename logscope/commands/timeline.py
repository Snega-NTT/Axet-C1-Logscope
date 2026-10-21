"""
logscope.commands.timeline
~~~~~~~~~~~~~~~~~~~~~~~~~~
Implements the ``logscope timeline`` command.

Reads a log file one line at a time (streaming; never read() / readlines()),
counts ERROR entries per time bucket, fills zero-count gaps, and returns a
:class:`TimelineResult` dataclass for formatting.

Bucket logic
------------
A timestamp is floored to its bucket boundary by zeroing seconds and rounding
the minute down to the nearest multiple of the bucket width::

    floor(ts, n_minutes) = ts.replace(
        minute = (ts.minute // n_minutes) * n_minutes,
        second = 0,
        microsecond = 0,
    )

Memory: O(number of buckets in the span of ERROR timestamps), which is bounded
by ``(last_error_ts - first_error_ts) / bucket_width``.  For a 100 MB file
spanning one day at 15-minute buckets that is at most 96 dict entries.
"""

from __future__ import annotations

import datetime
import pathlib
import re
from dataclasses import dataclass, field
from typing import Optional

from logscope.parser import parse_line

# ---------------------------------------------------------------------------
# Bucket-duration parsing
# ---------------------------------------------------------------------------

_BUCKET_RE = re.compile(r"^(?P<value>[1-9]\d*)(?P<unit>m)$")

# Supported minute values – extensible later (e.g. "1h").
_SUPPORTED_MINUTES = {1, 5, 10, 15, 30, 60}


class InvalidBucketError(ValueError):
    """Raised when the --bucket argument cannot be interpreted."""


def parse_bucket(raw: str) -> int:
    """Parse a bucket-duration string such as ``"15m"`` and return minutes.

    Args:
        raw: The raw CLI value, e.g. ``"15m"``, ``"1m"``, ``"60m"``.

    Returns:
        Integer number of minutes.

    Raises:
        :class:`InvalidBucketError`: For any value that is not a positive
            integer followed by ``m``, or that is zero / negative.
    """
    if not raw:
        raise InvalidBucketError("bucket duration must not be empty")

    m = _BUCKET_RE.match(raw.strip())
    if m is None:
        raise InvalidBucketError(
            f"invalid bucket value {raw!r}: expected a positive integer "
            f"followed by 'm', e.g. '1m', '5m', '15m', '60m'"
        )

    minutes = int(m.group("value"))
    if minutes <= 0:
        raise InvalidBucketError(
            f"invalid bucket value {raw!r}: must be a positive number of minutes"
        )

    return minutes


# ---------------------------------------------------------------------------
# Flooring helper
# ---------------------------------------------------------------------------


def floor_to_bucket(ts: datetime.datetime, bucket_minutes: int) -> datetime.datetime:
    """Return *ts* floored to the nearest *bucket_minutes* boundary."""
    floored_minute = (ts.minute // bucket_minutes) * bucket_minutes
    return ts.replace(minute=floored_minute, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class TimelineResult:
    """All data produced by a timeline scan of a log file.

    Attributes:
        bucket_minutes: Width of each time bucket in minutes.
        buckets:        Ordered list of ``(bucket_start, error_count)`` tuples
                        covering every slot from the first to the last bucket
                        that contains at least one ERROR, including zero-count
                        buckets in between.
        malformed_lines: Count of lines for which parse_line returned None.
    """

    bucket_minutes: int
    buckets: list[tuple[datetime.datetime, int]] = field(default_factory=list)
    malformed_lines: int = 0


# ---------------------------------------------------------------------------
# Core scan function
# ---------------------------------------------------------------------------


def run_timeline(log_path: pathlib.Path, bucket_minutes: int) -> TimelineResult:
    """Stream *log_path* line-by-line and return a :class:`TimelineResult`.

    Only ERROR entries contribute to bucket counts.  The returned bucket list
    covers the full range from the earliest to the latest error bucket,
    including any intermediate buckets with zero errors.

    Args:
        log_path:       Path to the log file.
        bucket_minutes: Bucket width in minutes (must be > 0).

    Returns:
        A populated :class:`TimelineResult`.

    Raises:
        OSError: If the file cannot be opened.
        ValueError: If ``bucket_minutes`` is not positive.
    """
    if bucket_minutes <= 0:
        raise ValueError(f"bucket_minutes must be positive, got {bucket_minutes}")

    # Sparse dict of bucket_start → error count (O(distinct buckets))
    counts: dict[datetime.datetime, int] = {}
    malformed: int = 0

    with log_path.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:                          # streaming — one line at a time
            entry = parse_line(raw)
            if entry is None:
                malformed += 1
                continue

            if entry.level != "ERROR":
                continue

            bucket = floor_to_bucket(entry.timestamp, bucket_minutes)
            counts[bucket] = counts.get(bucket, 0) + 1

    if not counts:
        return TimelineResult(bucket_minutes=bucket_minutes, buckets=[], malformed_lines=malformed)

    # Fill gaps between first and last bucket with zeros.
    first_bucket = min(counts)
    last_bucket  = max(counts)
    delta        = datetime.timedelta(minutes=bucket_minutes)

    buckets: list[tuple[datetime.datetime, int]] = []
    current = first_bucket
    while current <= last_bucket:
        buckets.append((current, counts.get(current, 0)))
        current += delta

    return TimelineResult(
        bucket_minutes=bucket_minutes,
        buckets=buckets,
        malformed_lines=malformed,
    )
