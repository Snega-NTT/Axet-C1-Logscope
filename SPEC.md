# LogScope CLI Specification

## Purpose

LogScope is a command-line tool for quickly analysing application log files after an incident, without using a dashboard.

The implementation may use Python or Node.js. Prefer the language and standard libraries that make streaming large files straightforward.

## Primary requirements

LogScope must provide these commands:

```text
logscope summary app.log
logscope timeline app.log --bucket 15m
logscope grep app.log --level ERROR --since "2026-10-01 09:00"
```text

Every command must support:

```text
--format json
--format md
```text

Default output may be a readable terminal/text format. `--format json` prints valid JSON to stdout. `--format md` writes a Markdown report file and prints its path.

## Log input format

The tool must inspect `sample.log` before finalising parser assumptions.

Primary supported format:

```text
2026-10-01 09:00:12 INFO Application started
2026-10-01 09:01:04 WARN Cache response was slow
2026-10-01 09:02:30 ERROR Database connection refused
```text

Expected fields:

1. Timestamp: `YYYY-MM-DD HH:MM:SS`
2. Level: `INFO`, `WARN`, or `ERROR`
3. Message: the rest of the line after the level

The parser should tolerate reasonable whitespace variations.

A line is malformed if it cannot produce a valid timestamp, supported level, and message. Malformed lines must be counted, skipped, and must never crash the program.

If the provided `sample.log` has a different format, update this specification with the exact observed format and make the parser support it.

## Command: `summary`

Usage:

```text
logscope summary <logfile> [--format json|md]
```text

Required output:

- Count of valid log entries by level:
  - `INFO`
  - `WARN`
  - `ERROR`
- Top 5 error messages, ordered by descending occurrence count
- First valid timestamp
- Last valid timestamp
- Count of malformed lines

Rules:

- Only entries with level `ERROR` are included in top-error aggregation.
- Repeated identical error messages are grouped together.
- If timestamps are out of order in the file, “first” and “last” mean the minimum and maximum valid timestamps, not merely the first and last lines read.
- Empty files and files with no valid lines must be handled gracefully.

## Command: `timeline`

Usage:

```text
logscope timeline <logfile> --bucket <duration> [--format json|md]
```text

Required options:

- `--bucket` is required.
- Initially support minute-based bucket durations such as:
  - `1m`
  - `5m`
  - `15m`
  - `60m`

Required output:

- Error count per time bucket.
- Only `ERROR` entries contribute to counts.
- Default terminal output is a readable text bar chart.
- The chart must include:
  - bucket start time
  - error count
  - proportional text bar, for example `#####`

Rules:

- Floor timestamps to their bucket boundary.
- Buckets with zero errors between the earliest and latest error timestamps should be shown where practical.
- Invalid bucket values must produce a clear error and non-zero exit code.
- Malformed-line count must be included in all output formats.

## Command: `grep`

Usage:

```text
logscope grep <logfile> [--level INFO|WARN|ERROR] [--since "<timestamp>"] [--format json|md]
```text

Required filters:

- `--level`: return only records with the exact specified level.
- `--since`: return records at or after the supplied timestamp.
- Both filters may be combined.
- If neither filter is supplied, return all valid entries.

Timestamp format for `--since`:

```text
YYYY-MM-DD HH:MM
```text

The implementation may also accept seconds (`YYYY-MM-DD HH:MM:SS`), but minute precision is required.

Required output:

- Matching log entries, preserving their original line content where possible.
- Number of matching entries.
- Count of malformed lines encountered while scanning.

Rules:

- An invalid `--since` value or invalid `--level` value must produce a clear error and non-zero exit code.
- The command must stream results and must not collect the entire matching file in memory.

## Output formats

### Default terminal output

- Human-readable and suitable for incident response.
- Clear headings and labels.
- Errors must go to stderr.
- Successful commands exit with code `0`.

### JSON output

- Must be valid JSON.
- Must have stable, documented field names.
- Must not mix non-JSON text into stdout.
- Diagnostic errors go to stderr.

Suggested JSON shapes:

```json
{
  "command": "summary",
  "levels": {"INFO": 10, "WARN": 2, "ERROR": 3},
  "top_errors": [{"message": "Database connection refused", "count": 2}],
  "first_timestamp": "2026-10-01T09:00:12",
  "last_timestamp": "2026-10-01T09:02:30",
  "malformed_lines": 1
}
```text

```json
{
  "command": "timeline",
  "bucket": "15m",
  "buckets": [{"start": "2026-10-01T09:00:00", "error_count": 2}],
  "malformed_lines": 1
}
```text

```json
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
```text

### Markdown output

- `--format md` must write a report file rather than only printing Markdown.
- Default report filename format:

```text
logscope-<command>-report.md
```text

- If a report file already exists, overwrite it only if the design explicitly documents that choice; otherwise create a unique filename.
- Print the generated report path to stdout.
- Markdown reports must include the same substantive information as the corresponding default/JSON output.

## Performance and memory requirements

- The tool must process a 100 MB log file in under 60 seconds on the local development environment.
- The tool must process log files line by line or through another streaming approach.
- It must not read the full file into memory.
- Memory usage should remain stable as file size grows.
- The implementation may retain bounded aggregate state required for results, such as:
  - counts by level
  - counts by error message
  - timeline bucket counts
- The implementation must document how runtime and memory were measured.

## Testing requirements

Create unit tests for:

1. Parser:
   - valid lines
   - whitespace variations
   - malformed timestamps
   - unsupported levels
   - missing messages
   - blank lines
2. `summary`:
   - counts by level
   - top 5 errors
   - first and last timestamps
   - malformed count
   - JSON output
   - Markdown report generation
3. `timeline`:
   - 15-minute bucketing
   - multiple buckets
   - zero-error buckets where applicable
   - invalid bucket handling
   - malformed count
4. `grep`:
   - level filter
   - since filter
   - combined filters
   - no-filter behaviour
   - invalid filter handling
   - JSON output
   - Markdown report generation
5. CLI behaviour:
   - exit codes
   - errors written to stderr
   - expected commands work against `sample.log`

All tests must pass before each feature commit.

## Synthetic log generator and benchmark

Create an executable generator:

```text
scripts/gen_log
```text

It must generate synthetic logs of a requested approximate size, including a configurable small proportion of malformed lines.

Example desired usage:

```text
scripts/gen_log --size 100MB --output tmp/synthetic-100mb.log
```text

Also provide a documented benchmark command that measures:

- elapsed runtime
- peak memory, where supported by the operating system

Run the benchmark against the 100 MB generated file and record:

- command used
- file size
- elapsed runtime
- peak memory measurement or an explicit note if unavailable
- pass/fail against the 60-second requirement

Store the results in `BENCHMARK.md`.

## Project quality requirements

- Use a clean CLI entry point named `logscope`.
- Include installation and usage instructions in `README.md`.
- Use type hints/type checking where practical for the selected language.
- Keep dependencies minimal.
- Do not silently ignore file errors, invalid arguments, or output-write failures.
- Ensure `.gitignore` excludes generated logs, reports, build output, virtual environments, and dependency directories.

## Stretch goal: `explain`

Optional command:

```text
logscope explain <logfile>
```text

Behaviour:

- Takes the most frequent error messages from the log.
- Sends them to an LLM endpoint configured solely through environment variables.
- Prints a probable root-cause summary.
- Must clearly state that the result is a hypothesis, not a confirmed diagnosis.
- Must not expose tokens or secrets in output, source control, or logs.
- The core required commands must be complete and tested before this feature begins.
