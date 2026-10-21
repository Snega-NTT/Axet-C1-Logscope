"""
logscope.output.markdown
~~~~~~~~~~~~~~~~~~~~~~~~
Markdown report writers for all LogScope commands.

Behaviour (documented per PLAN.md assumption D):
- Report filename: ``logscope-<command>-report.md``
- Written in the current working directory.
- If the file already exists it is **overwritten**.  In incident-response
  usage, re-running the command should always refresh the report.
- The report file path is printed to stdout on success.
- Nothing else goes to stdout.

Report content mirrors the JSON and terminal output for the same command.
"""

from __future__ import annotations

import datetime
import pathlib
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from logscope.commands.grep import GrepResult
    from logscope.commands.summary import SummaryResult
    from logscope.commands.timeline import TimelineResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _report_path(command: str, output_dir: pathlib.Path = pathlib.Path(".")) -> pathlib.Path:
    return output_dir / f"logscope-{command}-report.md"


def _fmt_ts(dt: Optional[datetime.datetime]) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt is not None else "N/A"


def _write_and_announce(path: pathlib.Path, content: str) -> None:
    """Write *content* to *path* (overwrite) and print the path to stdout."""
    path.write_text(content, encoding="utf-8")
    print(str(path))


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------


def write_summary_md(
    result: SummaryResult,
    output_dir: pathlib.Path = pathlib.Path("."),
) -> pathlib.Path:
    """Write a Markdown summary report and return the report path."""
    lines: list[str] = [
        "# LogScope — Summary Report\n",
        "## Log Levels\n",
        "| Level | Count |",
        "|-------|-------|",
    ]
    for level in ("INFO", "WARN", "ERROR"):
        lines.append(f"| {level} | {result.levels.get(level, 0)} |")

    lines += [
        "",
        "## Time Range\n",
        f"- **First entry:** {_fmt_ts(result.first_timestamp)}",
        f"- **Last entry:**  {_fmt_ts(result.last_timestamp)}",
        "",
        "## Top 5 Error Messages\n",
    ]
    if result.top_errors:
        lines += [
            "| Rank | Count | Message |",
            "|------|-------|---------|",
        ]
        for rank, (msg, count) in enumerate(result.top_errors, start=1):
            lines.append(f"| {rank} | {count} | {msg} |")
    else:
        lines.append("_No error entries found._")

    lines += [
        "",
        "## Data Quality\n",
        f"- **Malformed lines:** {result.malformed_lines}",
        "",
    ]

    path = _report_path("summary", output_dir)
    _write_and_announce(path, "\n".join(lines))
    return path


# ---------------------------------------------------------------------------
# timeline
# ---------------------------------------------------------------------------


def write_timeline_md(
    result: TimelineResult,
    output_dir: pathlib.Path = pathlib.Path("."),
) -> pathlib.Path:
    """Write a Markdown timeline report and return the report path."""
    lines: list[str] = [
        "# LogScope — Timeline Report\n",
        f"**Bucket width:** {result.bucket_minutes}m\n",
        "## Error Counts per Bucket\n",
    ]

    if result.buckets:
        max_count = max(c for _, c in result.buckets) or 1
        lines += [
            "| Bucket Start        | Errors | Bar |",
            "|---------------------|--------|-----|",
        ]
        for start, count in result.buckets:
            bar = "#" * round((count / max_count) * 20)
            lines.append(
                f"| {start.strftime('%Y-%m-%d %H:%M:%S')} | {count:>6} | {bar} |"
            )
    else:
        lines.append("_No ERROR entries found in the log file._")

    lines += [
        "",
        "## Data Quality\n",
        f"- **Malformed lines:** {result.malformed_lines}",
        "",
    ]

    path = _report_path("timeline", output_dir)
    _write_and_announce(path, "\n".join(lines))
    return path


# ---------------------------------------------------------------------------
# grep
# ---------------------------------------------------------------------------


def write_grep_md(
    result: GrepResult,
    entries: list[dict],
    output_dir: pathlib.Path = pathlib.Path("."),
) -> pathlib.Path:
    """Write a Markdown grep report and return the report path.

    Args:
        result:     The :class:`GrepResult` counters.
        entries:    List of entry dicts with keys
                    ``timestamp``, ``level``, ``message``, ``raw``.
        output_dir: Directory in which to write the report file.
    """
    filter_parts: list[str] = []
    if result.level_filter:
        filter_parts.append(f"level = `{result.level_filter}`")
    if result.since_filter:
        filter_parts.append(f"since = `{result.since_filter.strftime('%Y-%m-%d %H:%M:%S')}`")
    filter_str = ", ".join(filter_parts) if filter_parts else "_none (all valid entries)_"

    lines: list[str] = [
        "# LogScope — Grep Report\n",
        f"**Filters:** {filter_str}\n",
        f"**Matches:** {result.match_count}  |  **Malformed lines:** {result.malformed_lines}\n",
        "## Matching Entries\n",
    ]

    if entries:
        lines += [
            "| Timestamp           | Level | Message |",
            "|---------------------|-------|---------|",
        ]
        for e in entries:
            lines.append(f"| {e['timestamp']} | {e['level']} | {e['message']} |")
    else:
        lines.append("_No matching entries found._")

    lines.append("")

    path = _report_path("grep", output_dir)
    _write_and_announce(path, "\n".join(lines))
    return path
