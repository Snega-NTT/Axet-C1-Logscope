"""
tests.test_grep
~~~~~~~~~~~~~~~
Unit tests for logscope.commands.grep.

Run with:
    python -m pytest tests/test_grep.py -v
or:
    python -m unittest tests.test_grep -v
"""

from __future__ import annotations

import datetime
import io
import pathlib
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch


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


def _collect_grep(
    log_path: pathlib.Path,
    level_filter=None,
    since_filter=None,
) -> tuple[list[str], int, int]:
    """Run run_grep capturing stdout; return (lines, match_count, malformed)."""
    from logscope.commands.grep import run_grep

    buf = io.StringIO()
    with patch("sys.stdout", buf):
        result = run_grep(log_path, level_filter, since_filter)

    lines = [l for l in buf.getvalue().splitlines() if l]
    return lines, result.match_count, result.malformed_lines


# ---------------------------------------------------------------------------
# parse_since tests
# ---------------------------------------------------------------------------

class TestParseSince(unittest.TestCase):
    """parse_since accepts valid formats and rejects invalid ones."""

    def test_minute_precision(self) -> None:
        from logscope.commands.grep import parse_since
        dt = parse_since("2026-10-01 09:00")
        self.assertEqual(dt, _dt(2026, 10, 1, 9, 0, 0))

    def test_second_precision(self) -> None:
        from logscope.commands.grep import parse_since
        dt = parse_since("2026-10-01 09:00:30")
        self.assertEqual(dt, _dt(2026, 10, 1, 9, 0, 30))

    def test_leading_trailing_spaces_stripped(self) -> None:
        from logscope.commands.grep import parse_since
        dt = parse_since("  2026-10-01 09:15  ")
        self.assertEqual(dt, _dt(2026, 10, 1, 9, 15, 0))

    def test_invalid_format_raises(self) -> None:
        from logscope.commands.grep import InvalidSinceError, parse_since
        with self.assertRaises(InvalidSinceError):
            parse_since("not a date")

    def test_date_only_raises(self) -> None:
        from logscope.commands.grep import InvalidSinceError, parse_since
        with self.assertRaises(InvalidSinceError):
            parse_since("2026-10-01")

    def test_wrong_separator_raises(self) -> None:
        from logscope.commands.grep import InvalidSinceError, parse_since
        with self.assertRaises(InvalidSinceError):
            parse_since("2026/10/01 09:00")

    def test_empty_string_raises(self) -> None:
        from logscope.commands.grep import InvalidSinceError, parse_since
        with self.assertRaises(InvalidSinceError):
            parse_since("")

    def test_invalid_month_raises(self) -> None:
        from logscope.commands.grep import InvalidSinceError, parse_since
        with self.assertRaises(InvalidSinceError):
            parse_since("2026-13-01 09:00")


# ---------------------------------------------------------------------------
# validate_level tests
# ---------------------------------------------------------------------------

class TestValidateLevel(unittest.TestCase):
    """validate_level accepts INFO/WARN/ERROR and rejects others."""

    def test_info_accepted(self) -> None:
        from logscope.commands.grep import validate_level
        self.assertEqual(validate_level("INFO"), "INFO")

    def test_warn_accepted(self) -> None:
        from logscope.commands.grep import validate_level
        self.assertEqual(validate_level("WARN"), "WARN")

    def test_error_accepted(self) -> None:
        from logscope.commands.grep import validate_level
        self.assertEqual(validate_level("ERROR"), "ERROR")

    def test_lowercase_normalised(self) -> None:
        from logscope.commands.grep import validate_level
        self.assertEqual(validate_level("error"), "ERROR")

    def test_debug_rejected(self) -> None:
        from logscope.commands.grep import InvalidLevelError, validate_level
        with self.assertRaises(InvalidLevelError):
            validate_level("DEBUG")

    def test_unknown_rejected(self) -> None:
        from logscope.commands.grep import InvalidLevelError, validate_level
        with self.assertRaises(InvalidLevelError):
            validate_level("UNKNOWN")

    def test_empty_string_rejected(self) -> None:
        from logscope.commands.grep import InvalidLevelError, validate_level
        with self.assertRaises(InvalidLevelError):
            validate_level("")

    def test_numeric_rejected(self) -> None:
        from logscope.commands.grep import InvalidLevelError, validate_level
        with self.assertRaises(InvalidLevelError):
            validate_level("404")


# ---------------------------------------------------------------------------
# run_grep — level filter
# ---------------------------------------------------------------------------

class TestGrepLevelFilter(unittest.TestCase):
    """--level returns only entries with the exact specified level."""

    def test_level_error_returns_only_errors(self) -> None:
        log = _write_log(
            """\
            2026-10-01 09:00:00 INFO info line
            2026-10-01 09:01:00 WARN warn line
            2026-10-01 09:02:00 ERROR error one
            2026-10-01 09:03:00 ERROR error two
            """
        )
        lines, match_count, _ = _collect_grep(log, level_filter="ERROR")
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(match_count, 2)
        for line in lines:
            self.assertIn("ERROR", line)

    def test_level_info_returns_only_info(self) -> None:
        log = _write_log(
            """\
            2026-10-01 09:00:00 INFO alpha
            2026-10-01 09:01:00 WARN beta
            2026-10-01 09:02:00 ERROR gamma
            2026-10-01 09:03:00 INFO delta
            """
        )
        lines, match_count, _ = _collect_grep(log, level_filter="INFO")
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(match_count, 2)
        for line in lines:
            self.assertIn("INFO", line)

    def test_level_warn_returns_only_warn(self) -> None:
        log = _write_log(
            """\
            2026-10-01 09:00:00 INFO alpha
            2026-10-01 09:01:00 WARN beta
            2026-10-01 09:02:00 WARN gamma
            """
        )
        lines, match_count, _ = _collect_grep(log, level_filter="WARN")
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(match_count, 2)

    def test_level_filter_no_matches(self) -> None:
        log = _write_log(
            """\
            2026-10-01 09:00:00 INFO only info here
            """
        )
        lines, match_count, _ = _collect_grep(log, level_filter="ERROR")
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(match_count, 0)
        self.assertEqual(lines, [])


# ---------------------------------------------------------------------------
# run_grep — since filter
# ---------------------------------------------------------------------------

class TestGrepSinceFilter(unittest.TestCase):
    """--since returns only entries at or after the supplied timestamp."""

    def test_since_filters_earlier_entries(self) -> None:
        log = _write_log(
            """\
            2026-10-01 08:59:00 INFO before cutoff
            2026-10-01 09:00:00 INFO exactly at cutoff
            2026-10-01 09:01:00 INFO after cutoff
            """
        )
        since = _dt(2026, 10, 1, 9, 0, 0)
        lines, match_count, _ = _collect_grep(log, since_filter=since)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(match_count, 2)

    def test_since_inclusive_at_exact_second(self) -> None:
        """An entry whose timestamp exactly equals since must be included."""
        log = _write_log("2026-10-01 09:00:00 INFO exactly at boundary\n")
        since = _dt(2026, 10, 1, 9, 0, 0)
        _, match_count, _ = _collect_grep(log, since_filter=since)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(match_count, 1)

    def test_since_exclusive_one_second_before(self) -> None:
        """An entry one second before since must NOT be included."""
        log = _write_log("2026-10-01 08:59:59 INFO one second before\n")
        since = _dt(2026, 10, 1, 9, 0, 0)
        _, match_count, _ = _collect_grep(log, since_filter=since)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(match_count, 0)

    def test_since_no_matches(self) -> None:
        log = _write_log(
            """\
            2026-10-01 08:00:00 INFO early
            2026-10-01 08:30:00 WARN also early
            """
        )
        since = _dt(2026, 10, 1, 9, 0, 0)
        _, match_count, _ = _collect_grep(log, since_filter=since)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(match_count, 0)


# ---------------------------------------------------------------------------
# run_grep — combined filters
# ---------------------------------------------------------------------------

class TestGrepCombinedFilters(unittest.TestCase):
    """--level and --since may be combined (AND logic)."""

    def test_level_and_since_combined(self) -> None:
        log = _write_log(
            """\
            2026-10-01 08:58:00 ERROR before cutoff
            2026-10-01 09:00:00 INFO at cutoff but wrong level
            2026-10-01 09:02:00 ERROR matches both
            2026-10-01 09:05:00 ERROR also matches both
            """
        )
        since = _dt(2026, 10, 1, 9, 0, 0)
        lines, match_count, _ = _collect_grep(log, level_filter="ERROR", since_filter=since)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(match_count, 2)
        for line in lines:
            self.assertIn("ERROR", line)

    def test_combined_no_matches(self) -> None:
        log = _write_log(
            """\
            2026-10-01 09:02:00 INFO too early level match
            2026-10-01 09:10:00 WARN right time wrong level
            """
        )
        since = _dt(2026, 10, 1, 9, 5, 0)
        _, match_count, _ = _collect_grep(log, level_filter="ERROR", since_filter=since)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(match_count, 0)


# ---------------------------------------------------------------------------
# run_grep — no filters
# ---------------------------------------------------------------------------

class TestGrepNoFilters(unittest.TestCase):
    """With no filters, all valid entries are returned."""

    def test_no_filter_returns_all_valid(self) -> None:
        log = _write_log(
            """\
            2026-10-01 09:00:00 INFO alpha
            2026-10-01 09:01:00 WARN beta
            2026-10-01 09:02:00 ERROR gamma
            """
        )
        _, match_count, _ = _collect_grep(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(match_count, 3)

    def test_no_filter_skips_malformed(self) -> None:
        log = _write_log(
            """\
            2026-10-01 09:00:00 INFO valid
            THIS IS GARBAGE
            2026-10-01 09:01:00 WARN also valid
            """
        )
        _, match_count, malformed = _collect_grep(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(match_count, 2)
        self.assertEqual(malformed, 1)


# ---------------------------------------------------------------------------
# run_grep — raw line preservation
# ---------------------------------------------------------------------------

class TestGrepRawLinePreservation(unittest.TestCase):
    """Matched entries are printed using the original raw line."""

    def test_raw_line_matches_source(self) -> None:
        raw_line = "2026-10-01 09:02:30 ERROR Database connection refused"
        log = _write_log(raw_line + "\n")
        lines, _, _ = _collect_grep(log, level_filter="ERROR")
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], raw_line)


# ---------------------------------------------------------------------------
# run_grep — malformed lines
# ---------------------------------------------------------------------------

class TestGrepMalformedLines(unittest.TestCase):
    """Malformed lines are counted and never crash grep."""

    def test_malformed_count_accumulates(self) -> None:
        log = _write_log(
            """\
            garbage one
            2026-10-01 09:00:00 ERROR real
            garbage two
            garbage three
            """
        )
        _, _, malformed = _collect_grep(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(malformed, 3)

    def test_zero_malformed_on_clean_file(self) -> None:
        log = _write_log(
            """\
            2026-10-01 09:00:00 INFO clean
            2026-10-01 09:01:00 ERROR also clean
            """
        )
        _, _, malformed = _collect_grep(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(malformed, 0)

    def test_all_malformed_zero_matches(self) -> None:
        log = _write_log("bad\nworse\nterrible\n")
        _, match_count, malformed = _collect_grep(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(match_count, 0)
        self.assertEqual(malformed, 3)

    def test_empty_file(self) -> None:
        log = _write_log("")
        _, match_count, malformed = _collect_grep(log)
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertEqual(match_count, 0)
        self.assertEqual(malformed, 0)


# ---------------------------------------------------------------------------
# run_grep — missing / unreadable file
# ---------------------------------------------------------------------------

class TestGrepFileErrors(unittest.TestCase):
    """Missing files raise OSError."""

    def test_missing_file_raises_oserror(self) -> None:
        from logscope.commands.grep import run_grep

        with self.assertRaises(OSError):
            run_grep(pathlib.Path("/no/such/file.log"))


# ---------------------------------------------------------------------------
# Streaming behaviour
# ---------------------------------------------------------------------------

class TestGrepStreaming(unittest.TestCase):
    """iter_grep yields items one at a time without buffering all entries."""

    def test_iter_grep_yields_entries_lazily(self) -> None:
        from logscope.commands.grep import iter_grep

        log = _write_log(
            """\
            2026-10-01 09:00:00 ERROR first
            2026-10-01 09:01:00 ERROR second
            2026-10-01 09:02:00 ERROR third
            """
        )
        gen = iter_grep(log, level_filter="ERROR")
        first = next(gen)           # should not need to read whole file
        # Exhaust the generator to close the underlying file handle before
        # attempting deletion (required on Windows where open files are locked).
        for _ in gen:
            pass
        pathlib.Path(log).unlink(missing_ok=True)

        self.assertIsNotNone(first)
        self.assertEqual(first.level, "ERROR")  # type: ignore[union-attr]

    def test_iter_grep_yields_none_for_malformed(self) -> None:
        from logscope.commands.grep import iter_grep

        log = _write_log(
            """\
            GARBAGE
            2026-10-01 09:00:00 INFO valid
            """
        )
        items = list(iter_grep(log))
        pathlib.Path(log).unlink(missing_ok=True)

        # First yielded item should be None (malformed), second a LogEntry
        self.assertIsNone(items[0])
        self.assertIsNotNone(items[1])


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------

class TestGrepCLI(unittest.TestCase):
    """CLI-level tests for the grep subcommand."""

    def _run(self, *args: str) -> tuple[int, str, str]:
        result = subprocess.run(
            [sys.executable, "-m", "logscope", *args],
            capture_output=True,
            text=True,
            cwd=str(pathlib.Path(__file__).parent.parent),
        )
        return result.returncode, result.stdout, result.stderr

    def test_grep_exits_0_with_level_filter(self) -> None:
        rc, _, _ = self._run("grep", "sample.log", "--level", "ERROR")
        self.assertEqual(rc, 0)

    def test_grep_exits_0_with_since_filter(self) -> None:
        rc, _, _ = self._run("grep", "sample.log", "--since", "2026-10-01 09:00")
        self.assertEqual(rc, 0)

    def test_grep_exits_0_with_both_filters(self) -> None:
        rc, _, _ = self._run(
            "grep", "sample.log", "--level", "ERROR", "--since", "2026-10-01 09:00"
        )
        self.assertEqual(rc, 0)

    def test_grep_exits_0_with_no_filters(self) -> None:
        rc, _, _ = self._run("grep", "sample.log")
        self.assertEqual(rc, 0)

    def test_invalid_level_exits_nonzero(self) -> None:
        rc, stdout, stderr = self._run("grep", "sample.log", "--level", "DEBUG")
        self.assertNotEqual(rc, 0)
        self.assertIn("DEBUG", stderr)
        self.assertEqual(stdout, "")

    def test_invalid_since_exits_nonzero(self) -> None:
        rc, stdout, stderr = self._run("grep", "sample.log", "--since", "not-a-date")
        self.assertNotEqual(rc, 0)
        self.assertIn("not-a-date", stderr)
        self.assertEqual(stdout, "")

    def test_missing_level_value_exits_nonzero(self) -> None:
        """--level with no following value is an argparse error."""
        rc, _, stderr = self._run("grep", "sample.log", "--level")
        self.assertNotEqual(rc, 0)

    def test_missing_since_value_exits_nonzero(self) -> None:
        """--since with no following value is an argparse error."""
        rc, _, _ = self._run("grep", "sample.log", "--since")
        self.assertNotEqual(rc, 0)

    def test_missing_file_exits_nonzero(self) -> None:
        rc, stdout, stderr = self._run("grep", "no_such_file.log")
        self.assertNotEqual(rc, 0)
        self.assertIn("no_such_file.log", stderr)
        self.assertEqual(stdout, "")

    def test_error_goes_to_stderr_not_stdout(self) -> None:
        rc, stdout, stderr = self._run("grep", "sample.log", "--level", "BADLEVEL")
        self.assertNotEqual(rc, 0)
        self.assertEqual(stdout, "")
        self.assertIn("BADLEVEL", stderr)

    def test_stdout_contains_matched_lines(self) -> None:
        rc, stdout, _ = self._run("grep", "sample.log", "--level", "ERROR")
        self.assertEqual(rc, 0)
        self.assertIn("ERROR", stdout)

    def test_stdout_contains_match_count(self) -> None:
        rc, stdout, _ = self._run("grep", "sample.log", "--level", "ERROR")
        self.assertEqual(rc, 0)
        self.assertIn("Matches", stdout)

    def test_stdout_contains_malformed_count(self) -> None:
        rc, stdout, _ = self._run("grep", "sample.log", "--level", "ERROR")
        self.assertEqual(rc, 0)
        self.assertIn("Malformed", stdout)


# ---------------------------------------------------------------------------
# Integration test against sample.log
# ---------------------------------------------------------------------------

class TestGrepAgainstSampleLog(unittest.TestCase):
    """run_grep produces the expected results for the project sample.log."""

    def _sample_log(self) -> pathlib.Path:
        p = pathlib.Path(__file__).parent.parent / "sample.log"
        if not p.exists():
            self.skipTest("sample.log not found")
        return p

    def test_error_since_0900_match_count(self) -> None:
        since = _dt(2026, 10, 1, 9, 0, 0)
        _, match_count, _ = _collect_grep(
            self._sample_log(), level_filter="ERROR", since_filter=since
        )
        self.assertEqual(match_count, 5)

    def test_error_since_0900_malformed_count(self) -> None:
        since = _dt(2026, 10, 1, 9, 0, 0)
        _, _, malformed = _collect_grep(
            self._sample_log(), level_filter="ERROR", since_filter=since
        )
        self.assertEqual(malformed, 4)

    def test_error_since_0900_matched_lines_are_errors(self) -> None:
        since = _dt(2026, 10, 1, 9, 0, 0)
        lines, _, _ = _collect_grep(
            self._sample_log(), level_filter="ERROR", since_filter=since
        )
        for line in lines:
            self.assertIn("ERROR", line)

    def test_no_filter_match_count(self) -> None:
        """All 12 valid entries are returned when no filters are applied."""
        _, match_count, _ = _collect_grep(self._sample_log())
        self.assertEqual(match_count, 12)

    def test_no_filter_malformed_count(self) -> None:
        _, _, malformed = _collect_grep(self._sample_log())
        self.assertEqual(malformed, 4)

    def test_level_error_no_since_count(self) -> None:
        _, match_count, _ = _collect_grep(self._sample_log(), level_filter="ERROR")
        self.assertEqual(match_count, 5)

    def test_since_cutoff_before_all_entries(self) -> None:
        """Since before the first entry returns all valid entries."""
        since = _dt(2026, 10, 1, 8, 0, 0)
        _, match_count, _ = _collect_grep(self._sample_log(), since_filter=since)
        self.assertEqual(match_count, 12)

    def test_since_cutoff_after_all_entries(self) -> None:
        """Since after the last entry returns zero matches."""
        since = _dt(2026, 10, 1, 10, 0, 0)
        _, match_count, _ = _collect_grep(self._sample_log(), since_filter=since)
        self.assertEqual(match_count, 0)

    def test_first_entry_inclusive_since(self) -> None:
        """Since exactly at the first timestamp includes that entry."""
        since = _dt(2026, 10, 1, 8, 58, 10)
        _, match_count, _ = _collect_grep(self._sample_log(), since_filter=since)
        self.assertEqual(match_count, 12)

    def test_one_second_after_first_entry_excludes_it(self) -> None:
        since = _dt(2026, 10, 1, 8, 58, 11)
        _, match_count, _ = _collect_grep(self._sample_log(), since_filter=since)
        self.assertEqual(match_count, 11)


if __name__ == "__main__":
    unittest.main()
