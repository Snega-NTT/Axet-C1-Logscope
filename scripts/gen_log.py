#!/usr/bin/env python3
"""
scripts/gen_log
~~~~~~~~~~~~~~~
Synthetic log generator for LogScope benchmarking and testing.

Generates a log file in the exact LogScope format:

    YYYY-MM-DD HH:MM:SS LEVEL message

Output is written one line at a time; the full file is never held in memory.
Generation stops as soon as the cumulative byte count reaches the requested
size (at most one line of overshoot).

Usage
-----
    python scripts/gen_log --size 100MB --output tmp/synthetic-100mb.log
    python scripts/gen_log --size 10MB  --output tmp/test.log --malformed-percent 5
    python scripts/gen_log --size 1MB   --output tmp/tiny.log --seed 42

Options
-------
    --size BYTES       Target file size, e.g. 1MB, 10MB, 100MB, 500MB (required)
    --output PATH      Output file path (required); parent dirs are created
    --malformed-percent FLOAT
                       Percentage of lines to write as malformed (default: 1.0)
    --seed INT         Random seed for reproducibility (default: random)
"""

from __future__ import annotations

import argparse
import datetime
import pathlib
import random
import re
import sys

# ---------------------------------------------------------------------------
# Content catalogues
# ---------------------------------------------------------------------------

_LEVELS_WEIGHTS = [
    ("INFO",  60),
    ("WARN",  20),
    ("ERROR", 20),
]
_LEVELS  = [lv for lv, _ in _LEVELS_WEIGHTS]
_WEIGHTS = [w  for _,  w in _LEVELS_WEIGHTS]

_INFO_MESSAGES = [
    "Application started",
    "Configuration loaded",
    "Health check passed",
    "Connected to database",
    "Background job completed",
    "Retrying database connection",
    "Cache warmed up",
    "Scheduled task executed",
    "User session started",
    "Metrics flushed to backend",
]

_WARN_MESSAGES = [
    "Cache response was slow",
    "High memory usage detected",
    "Disk usage above 80%",
    "Response time exceeded threshold",
    "Retry attempt 1 of 3",
    "Rate limit approaching",
    "Degraded mode active",
    "Slow query detected",
]

# Small fixed catalogue so summary top-error aggregation remains efficient.
_ERROR_MESSAGES = [
    "Database connection refused",
    "Request timed out",
    "Out of memory",
    "Disk write failed",
    "Service unavailable",
]

_MALFORMED_LINES = [
    "this is a malformed log line",
    "FATAL something went wrong",
    "stacktrace at line 42",
    "---",
    "",
    "debug: internal state dump",
    "[SYSTEM] watchdog timeout",
]

_LEVEL_MESSAGES: dict[str, list[str]] = {
    "INFO":  _INFO_MESSAGES,
    "WARN":  _WARN_MESSAGES,
    "ERROR": _ERROR_MESSAGES,
}

# ---------------------------------------------------------------------------
# Size parsing
# ---------------------------------------------------------------------------

_SIZE_RE = re.compile(r"^(?P<value>\d+(?:\.\d+)?)(?P<unit>[KMG]?B?)$", re.IGNORECASE)
_MULTIPLIERS = {
    "":   1,
    "b":  1,
    "kb": 1_024,
    "mb": 1_024 ** 2,
    "gb": 1_024 ** 3,
}


def parse_size(raw: str) -> int:
    """Parse a human size string such as ``"100MB"`` and return bytes."""
    m = _SIZE_RE.match(raw.strip())
    if m is None:
        raise ValueError(
            f"invalid --size value {raw!r}: expected e.g. 1MB, 100MB, 1GB"
        )
    value = float(m.group("value"))
    unit  = m.group("unit").lower()
    mult  = _MULTIPLIERS.get(unit)
    if mult is None:
        raise ValueError(f"unknown size unit {m.group('unit')!r} in {raw!r}")
    return int(value * mult)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def generate(
    output_path: pathlib.Path,
    target_bytes: int,
    malformed_percent: float,
    seed: int,
) -> tuple[int, int, int]:
    """Write synthetic log lines to *output_path* until *target_bytes* are written.

    Args:
        output_path:       Destination file (parent dirs must exist).
        target_bytes:      Stop after writing at least this many bytes.
        malformed_percent: Fraction of lines to write as malformed (0–100).
        seed:              Random seed for reproducibility.

    Returns:
        Tuple of ``(actual_bytes, valid_count, malformed_count)``.
    """
    rng = random.Random(seed)

    # Timestamp starts at a plausible recent datetime and advances by a
    # small random delta each line so the file contains realistic ordering.
    ts = datetime.datetime(2026, 10, 1, 0, 0, 0)
    delta_seconds_range = (1, 10)

    malformed_threshold = malformed_percent / 100.0
    written_bytes = 0
    valid_count   = 0
    malformed_count = 0

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Open in binary mode so the newline is always exactly 1 byte (LF) on
    # every OS.  Text mode on Windows translates '\n' to '\r\n', making
    # the on-disk file larger than written_bytes would indicate.
    with output_path.open("wb") as fh:
        while written_bytes < target_bytes:
            # Advance timestamp
            ts += datetime.timedelta(
                seconds=rng.randint(*delta_seconds_range)
            )

            if rng.random() < malformed_threshold:
                line = rng.choice(_MALFORMED_LINES)
                malformed_count += 1
            else:
                level = rng.choices(_LEVELS, weights=_WEIGHTS, k=1)[0]
                message = rng.choice(_LEVEL_MESSAGES[level])
                line = f"{ts.strftime('%Y-%m-%d %H:%M:%S')} {level} {message}"
                valid_count += 1

            encoded = (line + "\n").encode("utf-8")
            fh.write(encoded)
            written_bytes += len(encoded)   # exact on-disk byte count

    return written_bytes, valid_count, malformed_count


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate a synthetic log file for LogScope benchmarking.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--size",
        required=True,
        metavar="BYTES",
        help="Target file size, e.g. 1MB, 10MB, 100MB.",
    )
    p.add_argument(
        "--output",
        required=True,
        type=pathlib.Path,
        metavar="PATH",
        help="Output file path; parent directories are created automatically.",
    )
    p.add_argument(
        "--malformed-percent",
        type=float,
        default=1.0,
        metavar="FLOAT",
        help="Percentage of lines to write as malformed (default: 1.0).",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=None,
        metavar="INT",
        help="Random seed for reproducibility (default: random).",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        target_bytes = parse_size(args.size)
    except ValueError as exc:
        print(f"gen_log: error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.malformed_percent < 0 or args.malformed_percent > 100:
        print(
            f"gen_log: error: --malformed-percent must be between 0 and 100",
            file=sys.stderr,
        )
        sys.exit(1)

    seed = args.seed if args.seed is not None else random.randrange(2**31)

    print(f"Generating {args.size} log -> {args.output}  (seed={seed}) ...", flush=True)

    actual_bytes, valid_count, malformed_count = generate(
        output_path=args.output,
        target_bytes=target_bytes,
        malformed_percent=args.malformed_percent,
        seed=seed,
    )

    print(
        f"Done.\n"
        f"  Output path    : {args.output}\n"
        f"  Actual size    : {actual_bytes:,} bytes "
        f"({actual_bytes / (1024**2):.2f} MB)\n"
        f"  Valid entries  : {valid_count:,}\n"
        f"  Malformed lines: {malformed_count:,}\n"
        f"  Seed           : {seed}"
    )


if __name__ == "__main__":
    main()
