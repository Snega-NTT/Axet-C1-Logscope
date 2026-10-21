#!/usr/bin/env python3
"""
scripts/benchmark.py
~~~~~~~~~~~~~~~~~~~~
Benchmarks the LogScope summary and timeline commands against a log file.

Measures elapsed wall-clock time (time.perf_counter) and peak Python heap
allocation (tracemalloc) for each command.  Both commands are run in-process
to eliminate subprocess startup overhead.

Usage
-----
    python scripts/benchmark.py --logfile tmp/synthetic-100mb.log

Options
-------
    --logfile PATH    Log file to benchmark against (required)
    --bucket DURATION Bucket width for timeline (default: 15m)
"""

from __future__ import annotations

import argparse
import pathlib
import platform
import sys
import time
import tracemalloc

_ROOT = pathlib.Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _measure(label: str, fn, *args, **kwargs) -> dict:
    """Run *fn*, return timing and tracemalloc peak-memory metrics."""
    tracemalloc.start()
    t0 = time.perf_counter()
    fn(*args, **kwargs)
    elapsed = time.perf_counter() - t0
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    passed = elapsed < 60.0
    result = {
        "label":           label,
        "elapsed_seconds": round(elapsed, 3),
        "peak_mb":         round(peak_bytes / (1024 ** 2), 2),
        "passed_60s":      passed,
    }
    status = "PASS" if passed else "FAIL"
    print(
        f"  {label}\n"
        f"    Elapsed  : {elapsed:.3f} s  [{status} < 60 s]\n"
        f"    Peak mem : {result['peak_mb']:.2f} MB  "
        f"(tracemalloc Python allocation peak)"
    )
    return result


def run_benchmarks(logfile: pathlib.Path, bucket: str = "15m") -> list[dict]:
    from logscope.commands.summary import run_summary
    from logscope.commands.timeline import parse_bucket, run_timeline

    size = logfile.stat().st_size
    bucket_minutes = parse_bucket(bucket)

    print(f"Python     : {platform.python_version()}")
    print(f"OS         : {platform.platform()}")
    print(f"File       : {logfile}")
    print(f"File size  : {size:,} bytes  ({size / (1024**2):.2f} MB)")
    print()

    results = [
        _measure("summary", run_summary, logfile),
        _measure(f"timeline --bucket {bucket}", run_timeline, logfile, bucket_minutes),
    ]

    all_pass = all(r["passed_60s"] for r in results)
    print()
    print(f"Performance criterion (< 60 s): {'ALL PASS' if all_pass else 'SOME FAIL'}")
    return results


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Benchmark LogScope commands.")
    p.add_argument("--logfile", required=True, type=pathlib.Path)
    p.add_argument("--bucket", default="15m")
    return p


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    if not args.logfile.exists():
        print(f"benchmark: error: file not found: {args.logfile}", file=sys.stderr)
        sys.exit(1)
    run_benchmarks(args.logfile, args.bucket)


if __name__ == "__main__":
    main()
