"""
tests.test_output
~~~~~~~~~~~~~~~~~
Unit and integration tests for JSON and Markdown output formats.

Tests cover:
  - JSON shape and field names for summary, timeline, grep
  - JSON validity (parseable by json.loads)
  - Markdown file creation and path announcement
  - Markdown report content (key headings and values present)
  - CLI --format json and --format md exit codes and behaviour
  - Overwrite behaviour for Markdown reports

Run with:
    python -m pytest tests/test_output.py -v
or:
    python -m unittest tests.test_output -v
"""

from __future__ import annotations

import datetime
import io
import json
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
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".log", delete=False, encoding="utf-8"
    )
    tmp.write(textwrap.dedent(content))
    tmp.flush()
    tmp.close()
    return pathlib.Path(tmp.name)


def _capture_stdout(fn, *args, **kwargs) -> str:
    buf = io.StringIO()
    with patch("sys.stdout", buf):
        fn(*args, **kwargs)
    return buf.getvalue()


def _run(*args: str) -> tuple[int, str, str]:
    result = subprocess.run(
        [sys.executable, "-m", "logscope", *args],
        capture_output=True,
        text=True,
        cwd=str(pathlib.Path(__file__).parent.parent),
    )
    return result.returncode, result.stdout, result.stderr


def _sample_log() -> pathlib.Path:
    return pathlib.Path(__file__).parent.parent / "sample.log"


# ---------------------------------------------------------------------------
# JSON — summary
# ---------------------------------------------------------------------------

class TestSummaryJSON(unittest.TestCase):
    """print_summary_json produces valid JSON with stable field names."""

    def _result(self):
        from logscope.commands.summary import run_summary
        return run_summary(_sample_log())

    def test_valid_json(self) -> None:
        from logscope.output.json_fmt import print_summary_json
        out = _capture_stdout(print_summary_json, self._result())
        parsed = json.loads(out)          # must not raise
        self.assertIsInstance(parsed, dict)

    def test_command_field(self) -> None:
        from logscope.output.json_fmt import print_summary_json
        parsed = json.loads(_capture_stdout(print_summary_json, self._result()))
        self.assertEqual(parsed["command"], "summary")

    def test_levels_field(self) -> None:
        from logscope.output.json_fmt import print_summary_json
        parsed = json.loads(_capture_stdout(print_summary_json, self._result()))
        self.assertIn("levels", parsed)
        self.assertEqual(parsed["levels"]["INFO"],  5)
        self.assertEqual(parsed["levels"]["WARN"],  2)
        self.assertEqual(parsed["levels"]["ERROR"], 5)

    def test_top_errors_field(self) -> None:
        from logscope.output.json_fmt import print_summary_json
        parsed = json.loads(_capture_stdout(print_summary_json, self._result()))
        self.assertIn("top_errors", parsed)
        self.assertIsInstance(parsed["top_errors"], list)
        first = parsed["top_errors"][0]
        self.assertIn("message", first)
        self.assertIn("count", first)
        self.assertEqual(first["message"], "Database connection refused")
        self.assertEqual(first["count"], 3)

    def test_timestamps_iso8601(self) -> None:
        from logscope.output.json_fmt import print_summary_json
        parsed = json.loads(_capture_stdout(print_summary_json, self._result()))
        self.assertEqual(parsed["first_timestamp"], "2026-10-01T08:58:10")
        self.assertEqual(parsed["last_timestamp"],  "2026-10-01T09:45:00")

    def test_malformed_lines_field(self) -> None:
        from logscope.output.json_fmt import print_summary_json
        parsed = json.loads(_capture_stdout(print_summary_json, self._result()))
        self.assertEqual(parsed["malformed_lines"], 4)

    def test_null_timestamps_when_no_valid_entries(self) -> None:
        from logscope.commands.summary import run_summary
        from logscope.output.json_fmt import print_summary_json
        log = _write_log("garbage\n")
        result = run_summary(log)
        pathlib.Path(log).unlink(missing_ok=True)
        parsed = json.loads(_capture_stdout(print_summary_json, result))
        self.assertIsNone(parsed["first_timestamp"])
        self.assertIsNone(parsed["last_timestamp"])

    def test_no_extra_text_on_stdout(self) -> None:
        """Nothing other than JSON must reach stdout."""
        from logscope.output.json_fmt import print_summary_json
        out = _capture_stdout(print_summary_json, self._result())
        json.loads(out)   # raises if extra text present
        self.assertFalse(out.strip().startswith("LogScope"))


# ---------------------------------------------------------------------------
# JSON — timeline
# ---------------------------------------------------------------------------

class TestTimelineJSON(unittest.TestCase):
    """print_timeline_json produces valid JSON with stable field names."""

    def _result(self):
        from logscope.commands.timeline import run_timeline
        return run_timeline(_sample_log(), 15)

    def test_valid_json(self) -> None:
        from logscope.output.json_fmt import print_timeline_json
        out = _capture_stdout(print_timeline_json, self._result())
        json.loads(out)

    def test_command_field(self) -> None:
        from logscope.output.json_fmt import print_timeline_json
        parsed = json.loads(_capture_stdout(print_timeline_json, self._result()))
        self.assertEqual(parsed["command"], "timeline")

    def test_bucket_field(self) -> None:
        from logscope.output.json_fmt import print_timeline_json
        parsed = json.loads(_capture_stdout(print_timeline_json, self._result()))
        self.assertEqual(parsed["bucket"], "15m")

    def test_buckets_structure(self) -> None:
        from logscope.output.json_fmt import print_timeline_json
        parsed = json.loads(_capture_stdout(print_timeline_json, self._result()))
        self.assertIsInstance(parsed["buckets"], list)
        self.assertEqual(len(parsed["buckets"]), 3)
        first = parsed["buckets"][0]
        self.assertIn("start", first)
        self.assertIn("error_count", first)

    def test_bucket_values_match_expected(self) -> None:
        from logscope.output.json_fmt import print_timeline_json
        parsed = json.loads(_capture_stdout(print_timeline_json, self._result()))
        buckets = {b["start"]: b["error_count"] for b in parsed["buckets"]}
        self.assertEqual(buckets["2026-10-01T09:00:00"], 2)
        self.assertEqual(buckets["2026-10-01T09:15:00"], 2)
        self.assertEqual(buckets["2026-10-01T09:30:00"], 1)

    def test_malformed_lines_field(self) -> None:
        from logscope.output.json_fmt import print_timeline_json
        parsed = json.loads(_capture_stdout(print_timeline_json, self._result()))
        self.assertEqual(parsed["malformed_lines"], 4)

    def test_empty_buckets_when_no_errors(self) -> None:
        from logscope.commands.timeline import run_timeline
        from logscope.output.json_fmt import print_timeline_json
        log = _write_log("2026-10-01 09:00:00 INFO no errors\n")
        result = run_timeline(log, 15)
        pathlib.Path(log).unlink(missing_ok=True)
        parsed = json.loads(_capture_stdout(print_timeline_json, result))
        self.assertEqual(parsed["buckets"], [])


# ---------------------------------------------------------------------------
# JSON — grep
# ---------------------------------------------------------------------------

class TestGrepJSON(unittest.TestCase):
    """print_grep_json produces valid JSON with stable field names."""

    def _run_json(self, level_filter=None, since_filter=None):
        from logscope.output.json_fmt import print_grep_json
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            result = print_grep_json(_sample_log(), level_filter, since_filter)
        return json.loads(buf.getvalue()), result

    def test_valid_json(self) -> None:
        parsed, _ = self._run_json(level_filter="ERROR")
        self.assertIsInstance(parsed, dict)

    def test_command_field(self) -> None:
        parsed, _ = self._run_json(level_filter="ERROR")
        self.assertEqual(parsed["command"], "grep")

    def test_filters_field_with_level(self) -> None:
        parsed, _ = self._run_json(level_filter="ERROR")
        self.assertEqual(parsed["filters"]["level"], "ERROR")
        self.assertNotIn("since", parsed["filters"])

    def test_filters_field_with_since(self) -> None:
        since = datetime.datetime(2026, 10, 1, 9, 0, 0)
        parsed, _ = self._run_json(since_filter=since)
        self.assertIn("since", parsed["filters"])
        self.assertEqual(parsed["filters"]["since"], "2026-10-01T09:00:00")

    def test_filters_empty_with_no_filters(self) -> None:
        parsed, _ = self._run_json()
        self.assertEqual(parsed["filters"], {})

    def test_match_count_field(self) -> None:
        parsed, result = self._run_json(level_filter="ERROR")
        self.assertEqual(parsed["match_count"], 5)
        self.assertEqual(result.match_count, 5)

    def test_entries_structure(self) -> None:
        parsed, _ = self._run_json(level_filter="ERROR")
        self.assertEqual(len(parsed["entries"]), 5)
        entry = parsed["entries"][0]
        for key in ("timestamp", "level", "message", "raw"):
            self.assertIn(key, entry)

    def test_entry_level_matches_filter(self) -> None:
        parsed, _ = self._run_json(level_filter="ERROR")
        for entry in parsed["entries"]:
            self.assertEqual(entry["level"], "ERROR")

    def test_malformed_lines_field(self) -> None:
        parsed, _ = self._run_json(level_filter="ERROR")
        self.assertEqual(parsed["malformed_lines"], 4)

    def test_no_matches_empty_entries(self) -> None:
        since = datetime.datetime(2026, 10, 1, 23, 0, 0)
        parsed, _ = self._run_json(since_filter=since)
        self.assertEqual(parsed["entries"], [])
        self.assertEqual(parsed["match_count"], 0)


# ---------------------------------------------------------------------------
# Markdown — summary
# ---------------------------------------------------------------------------

class TestSummaryMarkdown(unittest.TestCase):
    """write_summary_md creates a report file and prints only its path."""

    def _write(self, output_dir: pathlib.Path):
        from logscope.commands.summary import run_summary
        from logscope.output.markdown import write_summary_md
        result = run_summary(_sample_log())
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            path = write_summary_md(result, output_dir)
        return path, buf.getvalue().strip()

    def test_report_file_created(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path, _ = self._write(pathlib.Path(d))
            self.assertTrue(path.exists())

    def test_stdout_contains_only_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path, stdout = self._write(pathlib.Path(d))
            self.assertEqual(stdout, str(path))

    def test_filename(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path, _ = self._write(pathlib.Path(d))
            self.assertEqual(path.name, "logscope-summary-report.md")

    def test_report_contains_level_counts(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path, _ = self._write(pathlib.Path(d))
            content = path.read_text(encoding="utf-8")
            self.assertIn("INFO", content)
            self.assertIn("WARN", content)
            self.assertIn("ERROR", content)

    def test_report_contains_top_error(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path, _ = self._write(pathlib.Path(d))
            content = path.read_text(encoding="utf-8")
            self.assertIn("Database connection refused", content)

    def test_report_contains_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path, _ = self._write(pathlib.Path(d))
            content = path.read_text(encoding="utf-8")
            self.assertIn("08:58:10", content)
            self.assertIn("09:45:00", content)

    def test_report_contains_malformed_count(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path, _ = self._write(pathlib.Path(d))
            content = path.read_text(encoding="utf-8")
            self.assertIn("4", content)

    def test_overwrite_on_second_run(self) -> None:
        """Running twice must overwrite, not append."""
        with tempfile.TemporaryDirectory() as d:
            self._write(pathlib.Path(d))
            path, _ = self._write(pathlib.Path(d))
            content = path.read_text(encoding="utf-8")
            # If appended, "# LogScope" would appear twice
            self.assertEqual(content.count("# LogScope"), 1)


# ---------------------------------------------------------------------------
# Markdown — timeline
# ---------------------------------------------------------------------------

class TestTimelineMarkdown(unittest.TestCase):
    """write_timeline_md creates a report file and prints only its path."""

    def _write(self, output_dir: pathlib.Path):
        from logscope.commands.timeline import run_timeline
        from logscope.output.markdown import write_timeline_md
        result = run_timeline(_sample_log(), 15)
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            path = write_timeline_md(result, output_dir)
        return path, buf.getvalue().strip()

    def test_report_file_created(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path, _ = self._write(pathlib.Path(d))
            self.assertTrue(path.exists())

    def test_stdout_contains_only_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path, stdout = self._write(pathlib.Path(d))
            self.assertEqual(stdout, str(path))

    def test_filename(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path, _ = self._write(pathlib.Path(d))
            self.assertEqual(path.name, "logscope-timeline-report.md")

    def test_report_contains_bucket_start(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path, _ = self._write(pathlib.Path(d))
            content = path.read_text(encoding="utf-8")
            self.assertIn("2026-10-01 09:00:00", content)

    def test_report_contains_malformed_count(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path, _ = self._write(pathlib.Path(d))
            content = path.read_text(encoding="utf-8")
            self.assertIn("4", content)

    def test_overwrite_on_second_run(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            self._write(pathlib.Path(d))
            path, _ = self._write(pathlib.Path(d))
            self.assertEqual(path.read_text(encoding="utf-8").count("# LogScope"), 1)


# ---------------------------------------------------------------------------
# Markdown — grep
# ---------------------------------------------------------------------------

class TestGrepMarkdown(unittest.TestCase):
    """write_grep_md creates a report file and prints only its path."""

    def _write(self, output_dir: pathlib.Path, level_filter=None, since_filter=None):
        from logscope.commands.grep import GrepResult, iter_grep
        from logscope.output.markdown import write_grep_md

        entries = []
        malformed_lines = 0
        for item in iter_grep(_sample_log(), level_filter, since_filter):
            if item is None:
                malformed_lines += 1
            else:
                entries.append({
                    "timestamp": item.timestamp.isoformat(),
                    "level":     item.level,
                    "message":   item.message,
                    "raw":       item.raw,
                })

        result = GrepResult(
            match_count=len(entries),
            malformed_lines=malformed_lines,
            level_filter=level_filter,
            since_filter=since_filter,
        )
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            path = write_grep_md(result, entries, output_dir)
        return path, buf.getvalue().strip()

    def test_report_file_created(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path, _ = self._write(pathlib.Path(d), level_filter="ERROR")
            self.assertTrue(path.exists())

    def test_stdout_contains_only_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path, stdout = self._write(pathlib.Path(d), level_filter="ERROR")
            self.assertEqual(stdout, str(path))

    def test_filename(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path, _ = self._write(pathlib.Path(d))
            self.assertEqual(path.name, "logscope-grep-report.md")

    def test_report_contains_matched_entries(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path, _ = self._write(pathlib.Path(d), level_filter="ERROR")
            content = path.read_text(encoding="utf-8")
            self.assertIn("Database connection refused", content)

    def test_report_shows_no_filters_label(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path, _ = self._write(pathlib.Path(d))
            content = path.read_text(encoding="utf-8")
            self.assertIn("none", content.lower())

    def test_overwrite_on_second_run(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            self._write(pathlib.Path(d), level_filter="ERROR")
            path, _ = self._write(pathlib.Path(d), level_filter="ERROR")
            self.assertEqual(path.read_text(encoding="utf-8").count("# LogScope"), 1)


# ---------------------------------------------------------------------------
# CLI integration — --format json
# ---------------------------------------------------------------------------

class TestCLIFormatJSON(unittest.TestCase):
    """--format json produces valid JSON on stdout and exits 0."""

    def test_summary_format_json(self) -> None:
        rc, stdout, stderr = _run("summary", "sample.log", "--format", "json")
        self.assertEqual(rc, 0, stderr)
        parsed = json.loads(stdout)
        self.assertEqual(parsed["command"], "summary")

    def test_summary_json_no_extra_stdout(self) -> None:
        rc, stdout, _ = _run("summary", "sample.log", "--format", "json")
        self.assertEqual(rc, 0)
        # Must be parseable as a single JSON object
        json.loads(stdout)

    def test_timeline_format_json(self) -> None:
        rc, stdout, stderr = _run("timeline", "sample.log", "--bucket", "15m", "--format", "json")
        self.assertEqual(rc, 0, stderr)
        parsed = json.loads(stdout)
        self.assertEqual(parsed["command"], "timeline")

    def test_timeline_json_bucket_field(self) -> None:
        rc, stdout, _ = _run("timeline", "sample.log", "--bucket", "15m", "--format", "json")
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(stdout)["bucket"], "15m")

    def test_grep_format_json(self) -> None:
        rc, stdout, stderr = _run(
            "grep", "sample.log", "--level", "ERROR", "--format", "json"
        )
        self.assertEqual(rc, 0, stderr)
        parsed = json.loads(stdout)
        self.assertEqual(parsed["command"], "grep")

    def test_grep_json_entries_present(self) -> None:
        rc, stdout, _ = _run("grep", "sample.log", "--level", "ERROR", "--format", "json")
        self.assertEqual(rc, 0)
        parsed = json.loads(stdout)
        self.assertIsInstance(parsed["entries"], list)
        self.assertEqual(parsed["match_count"], 5)


# ---------------------------------------------------------------------------
# CLI integration — --format md
# ---------------------------------------------------------------------------

class TestCLIFormatMD(unittest.TestCase):
    """--format md writes a file and prints only the path on stdout."""

    def _cwd(self) -> pathlib.Path:
        return pathlib.Path(__file__).parent.parent

    def _report(self, command: str) -> pathlib.Path:
        return self._cwd() / f"logscope-{command}-report.md"

    def _cleanup(self, *commands: str) -> None:
        for cmd in commands:
            self._report(cmd).unlink(missing_ok=True)

    def test_summary_md_creates_file(self) -> None:
        self._cleanup("summary")
        rc, stdout, stderr = _run("summary", "sample.log", "--format", "md")
        self.assertEqual(rc, 0, stderr)
        reported_path = pathlib.Path(stdout.strip())
        self.assertTrue(reported_path.exists(), f"Report not found: {reported_path}")
        self._cleanup("summary")

    def test_summary_md_stdout_is_path_only(self) -> None:
        self._cleanup("summary")
        rc, stdout, _ = _run("summary", "sample.log", "--format", "md")
        self.assertEqual(rc, 0)
        # stdout must be exactly one line: the file path
        lines = [l for l in stdout.splitlines() if l.strip()]
        self.assertEqual(len(lines), 1)
        self._cleanup("summary")

    def test_timeline_md_creates_file(self) -> None:
        self._cleanup("timeline")
        rc, stdout, stderr = _run(
            "timeline", "sample.log", "--bucket", "15m", "--format", "md"
        )
        self.assertEqual(rc, 0, stderr)
        self.assertTrue(pathlib.Path(stdout.strip()).exists())
        self._cleanup("timeline")

    def test_grep_md_creates_file(self) -> None:
        self._cleanup("grep")
        rc, stdout, stderr = _run(
            "grep", "sample.log", "--level", "ERROR", "--format", "md"
        )
        self.assertEqual(rc, 0, stderr)
        self.assertTrue(pathlib.Path(stdout.strip()).exists())
        self._cleanup("grep")

    def test_md_does_not_write_json_to_stdout(self) -> None:
        self._cleanup("summary")
        rc, stdout, _ = _run("summary", "sample.log", "--format", "md")
        self.assertEqual(rc, 0)
        # stdout should NOT be parseable as JSON
        with self.assertRaises((json.JSONDecodeError, ValueError)):
            json.loads(stdout)
        self._cleanup("summary")


if __name__ == "__main__":
    unittest.main()
