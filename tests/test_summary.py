"""
tests.test_summary
~~~~~~~~~~~~~~~~~~
Unit tests for logscope.commands.summary.run_summary.

Run with:
    python -m pytest tests/test_summary.py -v
or:
    python -m unittest tests.test_summary -v
"""

from __future__ import annotations

import datetime
import pathlib
import tempfile
import textwrap
import unittest


def _write_log(content: str) -> pathlib.Path:
    """Write *content* to a temporary file and return its Path.

    The caller is responsible for cleanup; use inside a
    ``tempfile.TemporaryDirectory()`` context manager.
    """
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".log", delete=False, encoding="utf-8"
    )
    tmp.write(textwrap.dedent(content))
    tmp.flush()
    tmp.close()
    return pathlib.Path(tmp.name)


class TestSummaryLevelCounts(unittest.TestCase):
    """run_summary returns correct counts for each log level."""

    def test_counts_all_three_levels(self) -> None:
        from logscope.commands.summary import run_summary

        log = _write_log(
            """\
            2026-10-01 09:00:00 INFO  msg one
            2026-10-01 09:01:00 INFO  msg two
            2026-10-01 09:02:00 WARN  slow query
            2026-10-01 09:03:00 ERROR connection refused
            2026-10-01 09:04:00 ERROR timeout
            2026-10-01 09:05:00 ERROR disk full
            """
        )
        result = run_summary(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(result.levels["INFO"], 2)
        self.assertEqual(result.levels["WARN"], 1)
        self.assertEqual(result.levels["ERROR"], 3)

    def test_only_info_lines(self) -> None:
        from logscope.commands.summary import run_summary

        log = _write_log(
            """\
            2026-10-01 09:00:00 INFO alpha
            2026-10-01 09:01:00 INFO beta
            """
        )
        result = run_summary(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(result.levels["INFO"], 2)
        self.assertEqual(result.levels["WARN"], 0)
        self.assertEqual(result.levels["ERROR"], 0)

    def test_zero_counts_when_only_malformed(self) -> None:
        from logscope.commands.summary import run_summary

        log = _write_log("this is garbage\nanother bad line\n")
        result = run_summary(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(result.levels["INFO"], 0)
        self.assertEqual(result.levels["WARN"], 0)
        self.assertEqual(result.levels["ERROR"], 0)


class TestSummaryTopErrors(unittest.TestCase):
    """run_summary groups ERROR messages and returns the top 5."""

    def test_groups_repeated_error_messages(self) -> None:
        from logscope.commands.summary import run_summary

        log = _write_log(
            """\
            2026-10-01 09:00:00 ERROR Database connection refused
            2026-10-01 09:01:00 ERROR Database connection refused
            2026-10-01 09:02:00 ERROR Database connection refused
            2026-10-01 09:03:00 ERROR Out of memory
            """
        )
        result = run_summary(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(len(result.top_errors), 2)
        # Most-common first
        self.assertEqual(result.top_errors[0], ("Database connection refused", 3))
        self.assertEqual(result.top_errors[1], ("Out of memory", 1))

    def test_top_5_ordering_by_descending_count(self) -> None:
        from logscope.commands.summary import run_summary

        # Build 6 distinct ERROR messages with counts 6, 5, 4, 3, 2, 1.
        # Use a running minute counter so every generated timestamp is valid.
        repeated_lines = []
        minute = 0
        for i in range(6):
            repeat = 6 - i      # msg 0 → 6 occurrences … msg 5 → 1 occurrence
            for _ in range(repeat):
                h = minute // 60
                m = minute % 60
                repeated_lines.append(
                    f"2026-10-01 {h:02d}:{m:02d}:00 ERROR Error message {i}\n"
                )
                minute += 1

        log = _write_log("".join(repeated_lines))
        result = run_summary(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(len(result.top_errors), 5)
        counts = [count for _, count in result.top_errors]
        self.assertEqual(counts, sorted(counts, reverse=True),
                         "top_errors must be in descending order")

    def test_returns_at_most_5_errors(self) -> None:
        from logscope.commands.summary import run_summary

        lines = []
        for i in range(10):
            lines.append(f"2026-10-01 09:{i:02d}:00 ERROR Unique error {i}\n")
        log = _write_log("".join(lines))
        result = run_summary(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertLessEqual(len(result.top_errors), 5)

    def test_no_errors_gives_empty_top_errors(self) -> None:
        from logscope.commands.summary import run_summary

        log = _write_log(
            """\
            2026-10-01 09:00:00 INFO all good
            2026-10-01 09:01:00 WARN slightly concerning
            """
        )
        result = run_summary(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(result.top_errors, [])

    def test_only_error_entries_counted_in_top_errors(self) -> None:
        """INFO and WARN messages must not appear in top_errors."""
        from logscope.commands.summary import run_summary

        log = _write_log(
            """\
            2026-10-01 09:00:00 INFO repeated info message
            2026-10-01 09:01:00 INFO repeated info message
            2026-10-01 09:02:00 WARN repeated warn message
            2026-10-01 09:03:00 WARN repeated warn message
            2026-10-01 09:04:00 ERROR one error
            """
        )
        result = run_summary(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(len(result.top_errors), 1)
        self.assertEqual(result.top_errors[0][0], "one error")


class TestSummaryTimestamps(unittest.TestCase):
    """run_summary reports true min/max timestamps even in unsorted files."""

    def test_timestamps_in_order(self) -> None:
        from logscope.commands.summary import run_summary

        log = _write_log(
            """\
            2026-10-01 09:00:00 INFO first
            2026-10-01 09:01:00 INFO second
            2026-10-01 09:02:00 INFO third
            """
        )
        result = run_summary(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(result.first_timestamp, datetime.datetime(2026, 10, 1, 9, 0, 0))
        self.assertEqual(result.last_timestamp,  datetime.datetime(2026, 10, 1, 9, 2, 0))

    def test_earliest_timestamp_out_of_order(self) -> None:
        """First-line timestamp is NOT the earliest when file is unsorted."""
        from logscope.commands.summary import run_summary

        log = _write_log(
            """\
            2026-10-01 10:00:00 INFO late entry appears first
            2026-10-01 08:30:00 INFO early entry buried in middle
            2026-10-01 09:00:00 INFO middle entry
            """
        )
        result = run_summary(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(
            result.first_timestamp,
            datetime.datetime(2026, 10, 1, 8, 30, 0),
            "first_timestamp must be the minimum, not the first-line timestamp",
        )

    def test_latest_timestamp_out_of_order(self) -> None:
        """Last-line timestamp is NOT the latest when file is unsorted."""
        from logscope.commands.summary import run_summary

        log = _write_log(
            """\
            2026-10-01 10:00:00 INFO late entry appears first in file
            2026-10-01 08:30:00 INFO early entry
            2026-10-01 09:00:00 INFO middle entry is the last line
            """
        )
        result = run_summary(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(
            result.last_timestamp,
            datetime.datetime(2026, 10, 1, 10, 0, 0),
            "last_timestamp must be the maximum, not the last-line timestamp",
        )

    def test_single_entry_first_equals_last(self) -> None:
        from logscope.commands.summary import run_summary

        log = _write_log("2026-10-01 12:00:00 INFO only entry\n")
        result = run_summary(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(result.first_timestamp, result.last_timestamp)
        self.assertEqual(result.first_timestamp, datetime.datetime(2026, 10, 1, 12, 0, 0))

    def test_malformed_lines_do_not_affect_timestamps(self) -> None:
        from logscope.commands.summary import run_summary

        log = _write_log(
            """\
            THIS IS GARBAGE
            2026-10-01 09:00:00 INFO real entry
            MORE GARBAGE
            """
        )
        result = run_summary(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(result.first_timestamp, datetime.datetime(2026, 10, 1, 9, 0, 0))
        self.assertEqual(result.last_timestamp,  datetime.datetime(2026, 10, 1, 9, 0, 0))


class TestSummaryMalformedLines(unittest.TestCase):
    """run_summary counts malformed lines correctly."""

    def test_counts_malformed_lines(self) -> None:
        from logscope.commands.summary import run_summary

        log = _write_log(
            """\
            2026-10-01 09:00:00 INFO valid
            THIS IS GARBAGE
            2026-10-01 09:01:00 UNKNOWN unsupported level
            also garbage
            2026-10-01 09:02:00 ERROR valid error
            """
        )
        result = run_summary(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(result.malformed_lines, 3)

    def test_blank_lines_counted_as_malformed(self) -> None:
        from logscope.commands.summary import run_summary

        log = _write_log(
            """\
            2026-10-01 09:00:00 INFO valid

            2026-10-01 09:01:00 INFO also valid
            """
        )
        result = run_summary(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(result.malformed_lines, 1)

    def test_zero_malformed_on_clean_file(self) -> None:
        from logscope.commands.summary import run_summary

        log = _write_log(
            """\
            2026-10-01 09:00:00 INFO clean
            2026-10-01 09:01:00 WARN also clean
            """
        )
        result = run_summary(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(result.malformed_lines, 0)


class TestSummaryEdgeCases(unittest.TestCase):
    """run_summary handles edge-case files gracefully."""

    def test_empty_file(self) -> None:
        from logscope.commands.summary import run_summary

        log = _write_log("")
        result = run_summary(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(result.levels, {"INFO": 0, "WARN": 0, "ERROR": 0})
        self.assertEqual(result.top_errors, [])
        self.assertIsNone(result.first_timestamp)
        self.assertIsNone(result.last_timestamp)
        self.assertEqual(result.malformed_lines, 0)

    def test_only_malformed_lines(self) -> None:
        from logscope.commands.summary import run_summary

        log = _write_log("garbage\nmore garbage\nalso garbage\n")
        result = run_summary(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(result.levels, {"INFO": 0, "WARN": 0, "ERROR": 0})
        self.assertEqual(result.top_errors, [])
        self.assertIsNone(result.first_timestamp)
        self.assertIsNone(result.last_timestamp)
        self.assertEqual(result.malformed_lines, 3)

    def test_missing_file_raises_oserror(self) -> None:
        from logscope.commands.summary import run_summary

        missing = pathlib.Path("/nonexistent/path/no_such_file.log")
        with self.assertRaises(OSError):
            run_summary(missing)

    def test_single_malformed_line_file(self) -> None:
        from logscope.commands.summary import run_summary

        log = _write_log("not a log line\n")
        result = run_summary(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertIsNone(result.first_timestamp)
        self.assertIsNone(result.last_timestamp)
        self.assertEqual(result.malformed_lines, 1)


class TestSummaryAgainstSampleLog(unittest.TestCase):
    """Integration test: run_summary against the real sample.log."""

    def _sample_log(self) -> pathlib.Path:
        p = pathlib.Path(__file__).parent.parent / "sample.log"
        if not p.exists():
            self.skipTest("sample.log not found")
        return p

    def test_sample_log_does_not_crash(self) -> None:
        from logscope.commands.summary import run_summary

        result = run_summary(self._sample_log())
        # sample.log has 12 valid entries + 4 malformed
        total_valid = sum(result.levels.values())
        self.assertGreater(total_valid, 0)

    def test_sample_log_level_counts(self) -> None:
        from logscope.commands.summary import run_summary

        result = run_summary(self._sample_log())
        # sample.log: INFO=5, WARN=2, ERROR=5
        # malformed: plain-text line, invalid month 13, DEBUG level, WARN with no message
        self.assertEqual(result.levels["INFO"],  5)
        self.assertEqual(result.levels["WARN"],  2)
        self.assertEqual(result.levels["ERROR"], 5)

    def test_sample_log_malformed_count(self) -> None:
        from logscope.commands.summary import run_summary

        result = run_summary(self._sample_log())
        # malformed: plain-text line, invalid month (2026-13-01), DEBUG level, WARN with no message = 4
        self.assertEqual(result.malformed_lines, 4)

    def test_sample_log_top_error_most_common(self) -> None:
        from logscope.commands.summary import run_summary

        result = run_summary(self._sample_log())
        self.assertEqual(len(result.top_errors), 2)
        self.assertEqual(result.top_errors[0], ("Database connection refused", 3))
        self.assertEqual(result.top_errors[1], ("Request timed out", 2))

    def test_sample_log_timestamps(self) -> None:
        from logscope.commands.summary import run_summary

        result = run_summary(self._sample_log())
        self.assertEqual(result.first_timestamp, datetime.datetime(2026, 10, 1, 8, 58, 10))
        self.assertEqual(result.last_timestamp,  datetime.datetime(2026, 10, 1, 9, 45, 0))


if __name__ == "__main__":
    unittest.main()
