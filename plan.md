# LogScope — Approved Implementation Plan

## 1. Language choice: Python 3.12

**Rationale:** Python 3.12.10 is available on the development machine. Node.js is not. Python's standard library covers every requirement — `argparse` (CLI), `re` (parsing), `collections.Counter` (aggregation), `datetime` (timestamps), `pathlib` (file I/O), `json` (JSON output) — and file iteration is line-streaming by default. No third-party packages are required.

---

## 2. Project structure

```
logscope/
├── logscope/               # package
│   ├── __init__.py
│   ├── __main__.py         # `python -m logscope` entry point
│   ├── cli.py              # argparse setup, dispatches to commands
│   ├── parser.py           # log-line parser (pure functions, no I/O)
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── summary.py
│   │   ├── timeline.py
│   │   └── grep.py
│   └── output/
│       ├── __init__.py
│       ├── terminal.py     # human-readable formatters
│       ├── json_fmt.py     # JSON serialisers
│       └── markdown.py     # Markdown report writers
├── tests/
│   ├── test_parser.py
│   ├── test_summary.py
│   ├── test_timeline.py
│   ├── test_grep.py
│   └── test_cli.py
├── scripts/
│   └── gen_log             # synthetic log generator (Python, chmod +x)
├── sample.log
├── pyproject.toml          # [project] + [project.scripts] logscope = "logscope.cli:main"
├── README.md
├── BENCHMARK.md
└── .gitignore
```

The `logscope` command is installed via `pip install -e .` using `pyproject.toml`'s `[project.scripts]`. The command `python -m logscope` works without installation.

---

## 3. Parser rules (based on sample.log)

**Observed format:**
```
2026-10-01 09:00:12 INFO Application started
```

**Fields:**
1. Date: `YYYY-MM-DD`
2. Time: `HH:MM:SS`
3. Level: one of `INFO`, `WARN`, `ERROR` (exact, uppercase)
4. Message: remainder of the line (stripped)

**Regex:**
```python
LOG_RE = re.compile(
    r'^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<level>INFO|WARN|ERROR)\s+(?P<message>.+)$'
)
```

**Parser function signature:**
```python
@dataclass
class LogEntry:
    timestamp: datetime.datetime
    level: str          # "INFO" | "WARN" | "ERROR"
    message: str
    raw: str            # original line, stripped

def parse_line(raw: str) -> LogEntry | None:
    """Returns None for malformed lines. Never raises."""
```

**A line is malformed if any of:**
- Does not match `LOG_RE`
- Has a level not in `{INFO, WARN, ERROR}`
- Has an unparseable `datetime` (guarded by `try/except ValueError`)
- Is blank after stripping

---

## 4. Streaming and memory strategy

Every command opens the file with:
```python
open(path, 'r', encoding='utf-8', errors='replace')
```
and iterates line-by-line with `for line in fh:`. The full-file APIs `fh.read()` and `fh.readlines()` are never used.

**Bounded state retained per command:**

| Command  | Retained state                                                                 | Bounded by                                          |
|----------|--------------------------------------------------------------------------------|-----------------------------------------------------|
| summary  | 3 level counters, 1 Counter for error messages, 2 datetime vars (min/max), malformed count | O(unique error messages) — practically tiny |
| timeline | 1 dict[bucket_key → int], malformed count                                      | O(number of buckets in file span)                   |
| grep     | Streaming — yields/writes each match immediately; only malformed count and match count retained | O(1)                                   |

The `grep` command never accumulates entries in memory. For JSON output, a streaming approach is used: emit the opening brace and `"entries": [`, then write each entry with a comma separator, then close the array and object. This satisfies both the spec's no-full-memory-collection requirement and valid JSON output.

---

## 5. CLI design

```
logscope <command> <logfile> [options]

Commands:
  summary     Show counts, top errors, time range
  timeline    Bar chart of errors per time bucket
  grep        Filter log entries

Shared option (all commands):
  --format {json,md}   Output format (default: terminal text)

timeline options:
  --bucket DURATION    Required. Supported: 1m, 5m, 15m, 60m

grep options:
  --level LEVEL        Filter by level: INFO | WARN | ERROR
  --since TIMESTAMP    Filter entries at or after "YYYY-MM-DD HH:MM" or "YYYY-MM-DD HH:MM:SS"
```

Implemented with `argparse` sub-parsers. Invalid arguments produce a message on stderr and `sys.exit(1)`.

---

## 6. Output design

### Terminal (default)
Each command has a dedicated formatter in `output/terminal.py` producing labelled, aligned text. All errors and diagnostics go to stderr. Exit code 0 on success.

### JSON (`--format json`)
Each command serialises to a single JSON object matching the shapes in the spec. Output via `json.dumps(..., indent=2)` (or streaming equivalent for grep) to stdout. Nothing else goes to stdout.

**Documented JSON shapes:**

```json
// summary
{
  "command": "summary",
  "levels": {"INFO": 10, "WARN": 2, "ERROR": 3},
  "top_errors": [{"message": "Database connection refused", "count": 2}],
  "first_timestamp": "2026-10-01T09:00:12",
  "last_timestamp": "2026-10-01T09:02:30",
  "malformed_lines": 1
}

// timeline
{
  "command": "timeline",
  "bucket": "15m",
  "buckets": [{"start": "2026-10-01T09:00:00", "error_count": 2}],
  "malformed_lines": 1
}

// grep
{
  "command": "grep",
  "filters": {"level": "ERROR", "since": "2026-10-01T09:00:00"},
  "match_count": 1,
  "entries": [
    {
      "timestamp": "2026-10-01T09:02:30",
      "level": "ERROR",
      "message": "Database connection refused",
      "raw": "2026-10-01 09:02:30 ERROR Database connection refused"
    }
  ],
  "malformed_lines": 1
}
```

### Markdown (`--format md`)
- Writes `logscope-<command>-report.md` in the current working directory.
- **Documented overwrite behaviour:** if the file already exists it is overwritten. In incident-response usage, re-running the command should always refresh the report.
- Only the report file path is printed to stdout on success.
- The report contains the same substantive information as the terminal and JSON outputs.

---

## 7. Unit-test plan

All tests use Python's built-in `unittest`. They can also be run with `pytest` if installed.

### test_parser.py
- Valid standard line → correct `LogEntry` fields
- Extra internal whitespace between fields → still parsed
- Malformed timestamp (e.g. `9999-99-99`) → `None`
- Unsupported level (`UNKNOWN`) → `None`
- Missing message field → `None`
- Blank line → `None`
- Line with only whitespace → `None`

### test_summary.py
- Counts by level across mixed valid and invalid lines
- Top-5 errors: deduplication and descending order
- `first_timestamp` = minimum (not first-line) timestamp
- `last_timestamp` = maximum timestamp
- Malformed count accumulated correctly
- JSON output: all required keys present, correct types
- Markdown report: file created, path printed to stdout

### test_timeline.py
- 15m bucketing: two errors 1 second apart in same bucket → count 2
- Two errors 16 minutes apart → two separate buckets
- Zero-error buckets filled between earliest and latest error bucket
- Invalid bucket string `"7x"` → exits with code 1
- Malformed count included in all output formats

### test_grep.py
- `--level ERROR` returns only ERROR entries
- `--since "2026-10-01 09:15"` returns only entries at or after that time
- Combined `--level` + `--since` filters (AND logic)
- No filters → all valid entries returned
- Invalid `--level FOO` → exit code 1, message to stderr
- Invalid `--since "not a date"` → exit code 1, message to stderr
- JSON output: all required keys, entry structure matches spec
- Markdown report: file created, path printed to stdout

### test_cli.py
- `logscope summary sample.log` exits 0
- `logscope timeline sample.log --bucket 15m` exits 0
- `logscope grep sample.log --level ERROR` exits 0
- Non-existent log file → exit 1, message to stderr
- `logscope timeline sample.log` (missing `--bucket`) → exit 1
- `--format json` stdout is valid JSON (parseable by `json.loads`)
- `--format md` stdout is a file path, file exists on disk

---

## 8. Benchmark plan

### Synthetic log generator

```
python scripts/gen_log --size 100MB --output tmp/synthetic-100mb.log
```

- Generates lines in `YYYY-MM-DD HH:MM:SS LEVEL message` format
- Default ~5 % malformed lines (configurable via `--malformed-pct`)
- Timestamps advance monotonically with random jitter
- Writes line-by-line; never builds full content in memory
- Supports `--size` values like `100MB`, `10MB`, `1GB`

### Benchmark command

Cross-platform (Python timing wrapper):
```
python -c "
import time, subprocess, sys
t = time.perf_counter()
r = subprocess.run([sys.executable, '-m', 'logscope', 'summary', 'tmp/synthetic-100mb.log'])
print(f'Elapsed: {time.perf_counter() - t:.2f}s  exit={r.returncode}')
"
```

Memory measurement: `tracemalloc` is activated when the environment variable `LOGSCOPE_BENCH=1` is set. This adds negligible overhead and is disabled by default. Peak memory is reported to stderr at program exit.

### Results storage

Recorded in `BENCHMARK.md` with:
- Command used
- File size
- Elapsed runtime
- Peak memory (or explicit note if unavailable)
- Pass/fail against the 60-second requirement

---

## 9. Incremental commit plan

| # | Commit message | Content |
|---|---------------|---------|
| 1 | `plan: add SPEC.md, sample.log, project skeleton and .gitignore` | `SPEC.md`, `sample.log`, `pyproject.toml`, `README.md` skeleton, `.gitignore`, empty package stubs |
| 2 | `feat(parser): implement log-line parser with tests` | `logscope/parser.py`, `tests/test_parser.py`, all parser tests passing |
| 3 | `feat(summary): implement summary command with tests` | `logscope/commands/summary.py`, `logscope/output/` stubs, `tests/test_summary.py` |
| 4 | `feat(timeline): implement timeline command with tests` | `logscope/commands/timeline.py`, `tests/test_timeline.py` |
| 5 | `feat(grep): implement grep command with tests` | `logscope/commands/grep.py`, `tests/test_grep.py` |
| 6 | `feat(output): add JSON and Markdown output for all commands` | `logscope/output/json_fmt.py`, `logscope/output/markdown.py`, updated tests |
| 7 | `feat(cli): wire CLI entry point, add CLI tests` | `logscope/cli.py`, `logscope/__main__.py`, `tests/test_cli.py` |
| 8 | `feat(bench): add gen_log script, run 100 MB benchmark, document results` | `scripts/gen_log`, `BENCHMARK.md`, updated `README.md` |

---

## 10. Approved assumptions and documented decisions

| # | Item | Decision |
|---|------|----------|
| A | `sample.log` did not exist | Created to match the spec's example format exactly. Contains INFO, WARN, ERROR entries plus intentional malformed lines for testing. |
| B | `UNKNOWN` level lines | Treated as malformed — not a supported level per spec. |
| C | `grep` JSON streaming | Entries are emitted incrementally to stdout to avoid collecting the full result set in memory, satisfying the spec's streaming requirement. |
| D | Markdown overwrite | `logscope-<command>-report.md` is always overwritten on re-run. This is explicitly documented here per the spec's requirement. |
| E | `grep` with no filters | Returns all valid entries regardless of level or time. |
| F | Zero-error buckets in `timeline` | Filled only between the first and last bucket that contain errors, not from the start of the file. |
| G | Installation | `pip install -e .` from the project root installs the `logscope` entry point. `python -m logscope` always works without installation. |
| H | Build backend | `pyproject.toml` uses `hatchling` if available, otherwise `setuptools` as fallback. Will be confirmed during skeleton step. |
