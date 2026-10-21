"""
tests.test_timeline
~~~~~~~~~~~~~~~~~~~
Unit tests for logscope.commands.timeline.

Run with:
    python -m pytest tests/test_timeline.py -v
or:
    python -m unittest tests.test_timeline -v
"""

from __future__ import annotations

import datetime
import pathlib
import subprocess
import sys
import tempfile
import textwrap
import unittest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_log(content: str) -> pathlib.Path:
    """Write *content* to a named temp file and return its Path."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".log", delete=False, encoding="utf-8"
    )
    tmp.write(textwrap.dedent(content))
    tmp.flush()
    tmp.close()
    return pathlib.Path(tmp.name)


def _dt(y: int, mo: int, d: int, h: int, mi: int, s: int = 0) -> datetime.datetime:
    return datetime.datetime(y, mo, d, h, mi, s)


# ---------------------------------------------------------------------------
# parse_bucket tests
# ---------------------------------------------------------------------------

class TestParseBucket(unittest.TestCase):
    """parse_bucket accepts valid durations and rejects invalid ones."""

    def test_1m(self) -> None:
        from logscope.commands.timeline import parse_bucket
        self.assertEqual(parse_bucket("1m"), 1)

    def test_5m(self) -> None:
        from logscope.commands.timeline import parse_bucket
        self.assertEqual(parse_bucket("5m"), 5)

    def test_15m(self) -> None:
        from logscope.commands.timeline import parse_bucket
        self.assertEqual(parse_bucket("15m"), 15)

    def test_60m(self) -> None:
        from logscope.commands.timeline import parse_bucket
        self.assertEqual(parse_bucket("60m"), 60)

    def test_arbitrary_positive_minute(self) -> None:
        from logscope.commands.timeline import parse_bucket
        self.assertEqual(parse_bucket("7m"), 7)

    def test_invalid_unit_x(self) -> None:
        from logscope.commands.timeline import InvalidBucketError, parse_bucket
        with self.assertRaises(InvalidBucketError):
            parse_bucket("7x")

    def test_invalid_unit_h(self) -> None:
        from logscope.commands.timeline import InvalidBucketError, parse_bucket
        with self.assertRaises(InvalidBucketError):
            parse_bucket("1h")

    def test_zero_m(self) -> None:
        from logscope.commands.timeline import InvalidBucketError, parse_bucket
        with self.assertRaises(InvalidBucketError):
            parse_bucket("0m")

    def test_negative_not_matched(self) -> None:
        from logscope.commands.timeline import InvalidBucketError, parse_bucket
        with self.assertRaises(InvalidBucketError):
            parse_bucket("-5m")

    def test_empty_string(self) -> None:
        from logscope.commands.timeline import InvalidBucketError, parse_bucket
        with self.assertRaises(InvalidBucketError):
            parse_bucket("")

    def test_no_unit(self) -> None:
        from logscope.commands.timeline import InvalidBucketError, parse_bucket
        with self.assertRaises(InvalidBucketError):
            parse_bucket("15")

    def test_letters_only(self) -> None:
        from logscope.commands.timeline import InvalidBucketError, parse_bucket
        with self.assertRaises(InvalidBucketError):
            parse_bucket("abc")


# ---------------------------------------------------------------------------
# floor_to_bucket tests
# ---------------------------------------------------------------------------

class TestFloorToBucket(unittest.TestCase):
    """floor_to_bucket returns the correct bucket start datetime."""

    def test_already_on_boundary(self) -> None:
        from logscope.commands.timeline import floor_to_bucket
        ts = _dt(2026, 10, 1, 9, 15, 0)
        self.assertEqual(floor_to_bucket(ts, 15), _dt(2026, 10, 1, 9, 15, 0))

    def test_seconds_stripped(self) -> None:
        from logscope.commands.timeline import floor_to_bucket
        ts = _dt(2026, 10, 1, 9, 2, 30)
        self.assertEqual(floor_to_bucket(ts, 15), _dt(2026, 10, 1, 9, 0, 0))

    def test_minute_14_goes_to_0(self) -> None:
        from logscope.commands.timeline import floor_to_bucket
        ts = _dt(2026, 10, 1, 9, 14, 59)
        self.assertEqual(floor_to_bucket(ts, 15), _dt(2026, 10, 1, 9, 0, 0))

    def test_minute_15_stays_15(self) -> None:
        from logscope.commands.timeline import floor_to_bucket
        ts = _dt(2026, 10, 1, 9, 15, 1)
        self.assertEqual(floor_to_bucket(ts, 15), _dt(2026, 10, 1, 9, 15, 0))

    def test_minute_29_goes_to_15(self) -> None:
        from logscope.commands.timeline import floor_to_bucket
        ts = _dt(2026, 10, 1, 9, 29, 59)
        self.assertEqual(floor_to_bucket(ts, 15), _dt(2026, 10, 1, 9, 15, 0))

    def test_1m_bucket(self) -> None:
        from logscope.commands.timeline import floor_to_bucket
        ts = _dt(2026, 10, 1, 9, 7, 45)
        self.assertEqual(floor_to_bucket(ts, 1), _dt(2026, 10, 1, 9, 7, 0))

    def test_60m_bucket(self) -> None:
        from logscope.commands.timeline import floor_to_bucket
        ts = _dt(2026, 10, 1, 9, 45, 0)
        self.assertEqual(floor_to_bucket(ts, 60), _dt(2026, 10, 1, 9, 0, 0))


# ---------------------------------------------------------------------------
# run_timeline tests — bucketing logic
# ---------------------------------------------------------------------------

class TestTimelineBucketing(unittest.TestCase):
    """run_timeline places ERROR entries in the correct buckets."""

    def test_two_errors_same_bucket(self) -> None:
        """Two ERRORs within the same 15-minute window → count 2 in one bucket."""
        from logscope.commands.timeline import run_timeline

        log = _write_log(
            """\
            2026-10-01 09:02:30 ERROR Database connection refused
            2026-10-01 09:03:15 ERROR Database connection refused
            """
        )
        result = run_timeline(log, 15)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(len(result.buckets), 1)
        bucket_start, count = result.buckets[0]
        self.assertEqual(bucket_start, _dt(2026, 10, 1, 9, 0, 0))
        self.assertEqual(count, 2)

    def test_errors_in_different_buckets(self) -> None:
        """ERRORs 16 minutes apart → two separate buckets."""
        from logscope.commands.timeline import run_timeline

        log = _write_log(
            """\
            2026-10-01 09:02:30 ERROR first bucket
            2026-10-01 09:16:05 ERROR second bucket
            """
        )
        result = run_timeline(log, 15)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(len(result.buckets), 2)
        self.assertEqual(result.buckets[0], (_dt(2026, 10, 1, 9, 0, 0), 1))
        self.assertEqual(result.buckets[1], (_dt(2026, 10, 1, 9, 15, 0), 1))

    def test_zero_error_buckets_filled_between_error_buckets(self) -> None:
        """A gap between two error buckets is filled with a zero-count bucket."""
        from logscope.commands.timeline import run_timeline

        # bucket 09:00 → 1 error, bucket 09:15 → 0, bucket 09:30 → 1 error
        log = _write_log(
            """\
            2026-10-01 09:02:30 ERROR first
            2026-10-01 09:35:00 ERROR third
            """
        )
        result = run_timeline(log, 15)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(len(result.buckets), 3)
        self.assertEqual(result.buckets[0], (_dt(2026, 10, 1, 9, 0, 0), 1))
        self.assertEqual(result.buckets[1], (_dt(2026, 10, 1, 9, 15, 0), 0))  # zero-fill
        self.assertEqual(result.buckets[2], (_dt(2026, 10, 1, 9, 30, 0), 1))

    def test_multiple_zero_gaps_filled(self) -> None:
        """Two zero-count buckets between error buckets are both included."""
        from logscope.commands.timeline import run_timeline

        # bucket 09:00 → 1, 09:15 → 0, 09:30 → 0, 09:45 → 1
        log = _write_log(
            """\
            2026-10-01 09:01:00 ERROR early
            2026-10-01 09:50:00 ERROR late
            """
        )
        result = run_timeline(log, 15)
        pathlib.Path(log).unlink(missing_ok=True)

        bucket_starts = [b for b, _ in result.buckets]
        counts        = [c for _, c in result.buckets]

        self.assertEqual(bucket_starts[0],  _dt(2026, 10, 1, 9, 0, 0))
        self.assertEqual(bucket_starts[-1], _dt(2026, 10, 1, 9, 45, 0))
        # Inner buckets must be zero
        for c in counts[1:-1]:
            self.assertEqual(c, 0)

    def test_single_error_single_bucket(self) -> None:
        from logscope.commands.timeline import run_timeline

        log = _write_log("2026-10-01 09:05:00 ERROR lone error\n")
        result = run_timeline(log, 15)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(len(result.buckets), 1)
        self.assertEqual(result.buckets[0], (_dt(2026, 10, 1, 9, 0, 0), 1))

    def test_info_and_warn_not_counted(self) -> None:
        """Only ERROR entries contribute to bucket counts."""
        from logscope.commands.timeline import run_timeline

        log = _write_log(
            """\
            2026-10-01 09:00:00 INFO not counted
            2026-10-01 09:01:00 WARN not counted
            2026-10-01 09:02:00 ERROR counted
            """
        )
        result = run_timeline(log, 15)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(len(result.buckets), 1)
        self.assertEqual(result.buckets[0][1], 1)

    def test_1m_bucket(self) -> None:
        """1-minute bucket resolution places errors in separate 1-minute slots."""
        from logscope.commands.timeline import run_timeline

        log = _write_log(
            """\
            2026-10-01 09:01:05 ERROR first minute
            2026-10-01 09:01:55 ERROR also first minute
            2026-10-01 09:02:10 ERROR second minute
            """
        )
        result = run_timeline(log, 1)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(len(result.buckets), 2)
        self.assertEqual(result.buckets[0], (_dt(2026, 10, 1, 9, 1, 0), 2))
        self.assertEqual(result.buckets[1], (_dt(2026, 10, 1, 9, 2, 0), 1))

    def test_60m_bucket(self) -> None:
        """60-minute bucket groups all errors within the same hour."""
        from logscope.commands.timeline import run_timeline

        log = _write_log(
            """\
            2026-10-01 09:05:00 ERROR a
            2026-10-01 09:30:00 ERROR b
            2026-10-01 09:59:59 ERROR c
            """
        )
        result = run_timeline(log, 60)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(len(result.buckets), 1)
        self.assertEqual(result.buckets[0], (_dt(2026, 10, 1, 9, 0, 0), 3))


# ---------------------------------------------------------------------------
# run_timeline tests — malformed lines
# ---------------------------------------------------------------------------

class TestTimelineMalformed(unittest.TestCase):
    """run_timeline counts malformed lines correctly."""

    def test_malformed_lines_counted(self) -> None:
        from logscope.commands.timeline import run_timeline

        log = _write_log(
            """\
            garbage line
            2026-10-01 09:02:30 ERROR real error
            another bad line
            2026-10-01 09:50:00 DEBUG unsupported level
            """
        )
        result = run_timeline(log, 15)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(result.malformed_lines, 3)

    def test_malformed_lines_do_not_affect_buckets(self) -> None:
        from logscope.commands.timeline import run_timeline

        log = _write_log(
            """\
            GARBAGE
            2026-10-01 09:02:30 ERROR real
            MORE GARBAGE
            """
        )
        result = run_timeline(log, 15)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(len(result.buckets), 1)
        self.assertEqual(result.buckets[0][1], 1)
        self.assertEqual(result.malformed_lines, 2)

    def test_zero_malformed_on_clean_file(self) -> None:
        from logscope.commands.timeline import run_timeline

        log = _write_log(
            """\
            2026-10-01 09:00:00 INFO clean
            2026-10-01 09:01:00 ERROR also clean
            """
        )
        result = run_timeline(log, 15)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(result.malformed_lines, 0)


# ---------------------------------------------------------------------------
# run_timeline tests — edge cases
# ---------------------------------------------------------------------------

class TestTimelineEdgeCases(unittest.TestCase):
    """run_timeline handles edge cases gracefully."""

    def test_empty_file_no_buckets(self) -> None:
        from logscope.commands.timeline import run_timeline

        log = _write_log("")
        result = run_timeline(log, 15)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(result.buckets, [])
        self.assertEqual(result.malformed_lines, 0)

    def test_no_error_entries_no_buckets(self) -> None:
        from logscope.commands.timeline import run_timeline

        log = _write_log(
            """\
            2026-10-01 09:00:00 INFO no errors here
            2026-10-01 09:01:00 WARN just a warning
            """
        )
        result = run_timeline(log, 15)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(result.buckets, [])

    def test_only_malformed_no_buckets(self) -> None:
        from logscope.commands.timeline import run_timeline

        log = _write_log("garbage\nmore garbage\n")
        result = run_timeline(log, 15)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(result.buckets, [])
        self.assertEqual(result.malformed_lines, 2)

    def test_missing_file_raises_oserror(self) -> None:
        from logscope.commands.timeline import run_timeline

        with self.assertRaises(OSError):
            run_timeline(pathlib.Path("/no/such/file.log"), 15)

    def test_bucket_minutes_stored_in_result(self) -> None:
        from logscope.commands.timeline import run_timeline

        log = _write_log("2026-10-01 09:02:00 ERROR x\n")
        result = run_timeline(log, 15)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(result.bucket_minutes, 15)

    def test_buckets_are_in_ascending_order(self) -> None:
        from logscope.commands.timeline import run_timeline

        log = _write_log(
            """\
            2026-10-01 09:45:00 ERROR late
            2026-10-01 09:02:00 ERROR early
            """
        )
        result = run_timeline(log, 15)
        pathlib.Path(log).unlink(missing_ok=True)

        starts = [b for b, _ in result.buckets]
        self.assertEqual(starts, sorted(starts))


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------

class TestTimelineCLI(unittest.TestCase):
    """CLI-level tests for the timeline subcommand."""

    def _run(self, *args: str) -> tuple[int, str, str]:
        """Run ``python -m logscope <args>`` and return (returncode, stdout, stderr)."""
        result = subprocess.run(
            [sys.executable, "-m", "logscope", *args],
            capture_output=True,
            text=True,
            cwd=str(pathlib.Path(__file__).parent.parent),
        )
        return result.returncode, result.stdout, result.stderr

    def test_timeline_exits_0_on_valid_input(self) -> None:
        rc, _, _ = self._run("timeline", "sample.log", "--bucket", "15m")
        self.assertEqual(rc, 0)

    def test_missing_bucket_exits_nonzero(self) -> None:
        rc, _, stderr = self._run("timeline", "sample.log")
        self.assertNotEqual(rc, 0)
        # argparse should mention --bucket in the error
        self.assertIn("bucket", stderr.lower())

    def test_invalid_bucket_7x_exits_nonzero(self) -> None:
        rc, _, stderr = self._run("timeline", "sample.log", "--bucket", "7x")
        self.assertNotEqual(rc, 0)
        self.assertIn("7x", stderr)

    def test_invalid_bucket_0m_exits_nonzero(self) -> None:
        rc, _, stderr = self._run("timeline", "sample.log", "--bucket", "0m")
        self.assertNotEqual(rc, 0)

    def test_missing_file_exits_nonzero(self) -> None:
        rc, _, stderr = self._run("timeline", "no_such_file.log", "--bucket", "15m")
        self.assertNotEqual(rc, 0)
        self.assertIn("no_such_file.log", stderr)

    def test_stdout_contains_bucket_start_timestamp(self) -> None:
        rc, stdout, _ = self._run("timeline", "sample.log", "--bucket", "15m")
        self.assertEqual(rc, 0)
        self.assertIn("2026-10-01 09:00:00", stdout)

    def test_stdout_contains_malformed_count(self) -> None:
        rc, stdout, _ = self._run("timeline", "sample.log", "--bucket", "15m")
        self.assertEqual(rc, 0)
        self.assertIn("Malformed", stdout)

    def test_error_output_goes_to_stderr_not_stdout(self) -> None:
        rc, stdout, stderr = self._run("timeline", "sample.log", "--bucket", "7x")
        self.assertNotEqual(rc, 0)
        self.assertEqual(stdout, "")
        self.assertIn("7x", stderr)


# ---------------------------------------------------------------------------
# Integration test against sample.log
# ---------------------------------------------------------------------------

class TestTimelineAgainstSampleLog(unittest.TestCase):
    """run_timeline produces the expected buckets for the project sample.log."""

    def _sample_log(self) -> pathlib.Path:
        p = pathlib.Path(__file__).parent.parent / "sample.log"
        if not p.exists():
            self.skipTest("sample.log not found")
        return p

    def test_sample_log_bucket_count(self) -> None:
        from logscope.commands.timeline import run_timeline

        result = run_timeline(self._sample_log(), 15)
        # Expect exactly 3 buckets: 09:00, 09:15, 09:30 (adjacent, no gaps)
        self.assertEqual(len(result.buckets), 3)

    def test_sample_log_bucket_09_00(self) -> None:
        from logscope.commands.timeline import run_timeline

        result = run_timeline(self._sample_log(), 15)
        self.assertEqual(result.buckets[0], (_dt(2026, 10, 1, 9, 0, 0), 2))

    def test_sample_log_bucket_09_15(self) -> None:
        from logscope.commands.timeline import run_timeline

        result = run_timeline(self._sample_log(), 15)
        self.assertEqual(result.buckets[1], (_dt(2026, 10, 1, 9, 15, 0), 2))

    def test_sample_log_bucket_09_30(self) -> None:
        from logscope.commands.timeline import run_timeline

        result = run_timeline(self._sample_log(), 15)
        self.assertEqual(result.buckets[2], (_dt(2026, 10, 1, 9, 30, 0), 1))

    def test_sample_log_malformed_count(self) -> None:
        from logscope.commands.timeline import run_timeline

        result = run_timeline(self._sample_log(), 15)
        self.assertEqual(result.malformed_lines, 4)

    def test_sample_log_total_errors(self) -> None:
        from logscope.commands.timeline import run_timeline

        result = run_timeline(self._sample_log(), 15)
        total = sum(c for _, c in result.buckets)
        self.assertEqual(total, 5)


if __name__ == "__main__":
    unittest.main()
