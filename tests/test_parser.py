"""
tests.test_parser
~~~~~~~~~~~~~~~~~
Unit tests for logscope.parser.parse_line.

Run with:
    python -m pytest tests/test_parser.py -v
or without pytest:
    python -m unittest tests.test_parser -v
"""

from __future__ import annotations

import datetime
import unittest

from logscope.parser import LogEntry, parse_line


class TestParseLineValid(unittest.TestCase):
    """parse_line returns a correct LogEntry for well-formed lines."""

    def test_valid_info_line(self) -> None:
        raw = "2026-10-01 09:00:12 INFO Application started"
        entry = parse_line(raw)
        self.assertIsNotNone(entry)
        assert entry is not None  # narrow type for mypy
        self.assertIsInstance(entry, LogEntry)
        self.assertEqual(entry.timestamp, datetime.datetime(2026, 10, 1, 9, 0, 12))
        self.assertEqual(entry.level, "INFO")
        self.assertEqual(entry.message, "Application started")
        self.assertEqual(entry.raw, raw)

    def test_valid_warn_line(self) -> None:
        raw = "2026-10-01 09:01:04 WARN Cache response was slow"
        entry = parse_line(raw)
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.level, "WARN")
        self.assertEqual(entry.message, "Cache response was slow")

    def test_valid_error_line(self) -> None:
        raw = "2026-10-01 09:02:30 ERROR Database connection refused"
        entry = parse_line(raw)
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.level, "ERROR")
        self.assertEqual(entry.message, "Database connection refused")

    def test_raw_preserves_original_text(self) -> None:
        """raw must equal the line with only trailing newline stripped."""
        raw = "2026-10-01 09:00:12 INFO Application started"
        entry = parse_line(raw + "\n")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.raw, raw)

    def test_raw_preserves_original_text_crlf(self) -> None:
        raw = "2026-10-01 09:00:12 INFO Windows line ending"
        entry = parse_line(raw + "\r\n")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.raw, raw)

    def test_message_with_multiple_words_and_punctuation(self) -> None:
        raw = "2026-10-01 10:30:00 ERROR Disk I/O error on /dev/sda1: retrying (3/5)"
        entry = parse_line(raw)
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.message, "Disk I/O error on /dev/sda1: retrying (3/5)")

    def test_single_word_message(self) -> None:
        raw = "2026-10-01 00:00:00 INFO Startup"
        entry = parse_line(raw)
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.message, "Startup")

    def test_timestamp_midnight(self) -> None:
        raw = "2026-01-01 00:00:00 INFO Midnight boot"
        entry = parse_line(raw)
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.timestamp, datetime.datetime(2026, 1, 1, 0, 0, 0))

    def test_timestamp_end_of_day(self) -> None:
        raw = "2026-12-31 23:59:59 WARN Day ending"
        entry = parse_line(raw)
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.timestamp, datetime.datetime(2026, 12, 31, 23, 59, 59))


class TestParseLineWhitespace(unittest.TestCase):
    """parse_line tolerates reasonable whitespace variations."""

    def test_double_space_between_fields(self) -> None:
        """Two spaces between every field should still parse."""
        raw = "2026-10-01  09:00:12  INFO  Multiple spaces between fields"
        entry = parse_line(raw)
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.level, "INFO")
        self.assertEqual(entry.message, "Multiple spaces between fields")

    def test_tab_between_fields(self) -> None:
        """Tabs used as separators should still parse."""
        raw = "2026-10-01\t09:00:12\tINFO\tTab separated line"
        entry = parse_line(raw)
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.level, "INFO")
        self.assertEqual(entry.message, "Tab separated line")

    def test_trailing_whitespace_on_line(self) -> None:
        """Trailing spaces should not affect parsing."""
        raw = "2026-10-01 09:00:12 INFO Trailing spaces   "
        entry = parse_line(raw)
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.message, "Trailing spaces")

    def test_leading_whitespace_makes_line_malformed(self) -> None:
        """A leading space before the date breaks the expected format."""
        raw = " 2026-10-01 09:00:12 INFO Leading space"
        entry = parse_line(raw)
        self.assertIsNone(entry)


class TestParseLineBlankLines(unittest.TestCase):
    """parse_line returns None for blank and whitespace-only lines."""

    def test_empty_string(self) -> None:
        self.assertIsNone(parse_line(""))

    def test_newline_only(self) -> None:
        self.assertIsNone(parse_line("\n"))

    def test_crlf_only(self) -> None:
        self.assertIsNone(parse_line("\r\n"))

    def test_spaces_only(self) -> None:
        self.assertIsNone(parse_line("   "))

    def test_tab_only(self) -> None:
        self.assertIsNone(parse_line("\t"))


class TestParseLineInvalidTimestamp(unittest.TestCase):
    """parse_line returns None when the timestamp is structurally present but invalid."""

    def test_invalid_month_13(self) -> None:
        raw = "2026-13-01 09:00:12 INFO Bad month"
        self.assertIsNone(parse_line(raw))

    def test_invalid_day_32(self) -> None:
        raw = "2026-10-32 09:00:12 INFO Bad day"
        self.assertIsNone(parse_line(raw))

    def test_invalid_hour_25(self) -> None:
        raw = "2026-10-01 25:00:00 INFO Bad hour"
        self.assertIsNone(parse_line(raw))

    def test_invalid_minute_60(self) -> None:
        raw = "2026-10-01 09:60:00 INFO Bad minute"
        self.assertIsNone(parse_line(raw))

    def test_invalid_second_61(self) -> None:
        raw = "2026-10-01 09:00:61 INFO Bad second"
        self.assertIsNone(parse_line(raw))

    def test_date_letters_instead_of_digits(self) -> None:
        raw = "YYYY-MM-DD 09:00:00 INFO Not a date"
        self.assertIsNone(parse_line(raw))

    def test_missing_time_component(self) -> None:
        raw = "2026-10-01 INFO No time"
        self.assertIsNone(parse_line(raw))

    def test_date_only_no_time(self) -> None:
        raw = "2026-10-01 INFO Missing time field"
        self.assertIsNone(parse_line(raw))


class TestParseLineUnsupportedLevel(unittest.TestCase):
    """parse_line returns None for levels outside {INFO, WARN, ERROR}."""

    def test_unknown_level(self) -> None:
        raw = "2026-10-01 09:00:00 UNKNOWN unsupported level"
        self.assertIsNone(parse_line(raw))

    def test_debug_level(self) -> None:
        raw = "2026-10-01 09:00:00 DEBUG debug message"
        self.assertIsNone(parse_line(raw))

    def test_trace_level(self) -> None:
        raw = "2026-10-01 09:00:00 TRACE trace message"
        self.assertIsNone(parse_line(raw))

    def test_fatal_level(self) -> None:
        raw = "2026-10-01 09:00:00 FATAL fatal message"
        self.assertIsNone(parse_line(raw))

    def test_lowercase_info_is_malformed(self) -> None:
        """Level matching is case-sensitive; lowercase is malformed."""
        raw = "2026-10-01 09:00:00 info lowercase level"
        self.assertIsNone(parse_line(raw))

    def test_mixed_case_level_is_malformed(self) -> None:
        raw = "2026-10-01 09:00:00 Info Mixed case level"
        self.assertIsNone(parse_line(raw))

    def test_numeric_level(self) -> None:
        raw = "2026-10-01 09:00:00 404 numeric level"
        self.assertIsNone(parse_line(raw))


class TestParseLineMissingMessage(unittest.TestCase):
    """parse_line returns None when the message field is absent or empty."""

    def test_no_message_after_level(self) -> None:
        """Line ends immediately after the level token."""
        raw = "2026-10-01 09:00:00 INFO"
        self.assertIsNone(parse_line(raw))

    def test_only_whitespace_after_level(self) -> None:
        """Message is only spaces — treated as absent."""
        raw = "2026-10-01 09:00:00 INFO    "
        self.assertIsNone(parse_line(raw))

    def test_no_message_error_level(self) -> None:
        raw = "2026-10-01 09:00:00 ERROR"
        self.assertIsNone(parse_line(raw))


class TestParseLineArbitraryGarbage(unittest.TestCase):
    """parse_line handles completely unstructured input without raising."""

    def test_plain_text_sentence(self) -> None:
        self.assertIsNone(parse_line("THIS LINE IS MALFORMED and should be counted"))

    def test_json_fragment(self) -> None:
        self.assertIsNone(parse_line('{"key": "value"}'))

    def test_stack_trace_line(self) -> None:
        self.assertIsNone(parse_line("    at com.example.App.main(App.java:42)"))

    def test_separator_line(self) -> None:
        self.assertIsNone(parse_line("----------------------------"))

    def test_very_long_garbage_line(self) -> None:
        self.assertIsNone(parse_line("x" * 10_000))


class TestParseLineSampleLog(unittest.TestCase):
    """Integration-style: parse every line of sample.log without crashing."""

    def test_sample_log_does_not_crash(self) -> None:
        """All lines in sample.log must be parsed without raising any exception."""
        import pathlib

        sample = pathlib.Path(__file__).parent.parent / "sample.log"
        if not sample.exists():
            self.skipTest("sample.log not found")

        valid = 0
        malformed = 0
        with sample.open("r", encoding="utf-8", errors="replace") as fh:
            for raw in fh:          # streaming — one line at a time
                result = parse_line(raw)
                if result is None:
                    malformed += 1
                else:
                    valid += 1

        # sample.log has known valid entries; basic sanity check
        self.assertGreater(valid, 0, "Expected at least one valid entry in sample.log")
        self.assertGreater(malformed, 0, "Expected at least one malformed line in sample.log")


if __name__ == "__main__":
    unittest.main()
