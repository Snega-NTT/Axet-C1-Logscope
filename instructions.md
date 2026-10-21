# aXet Code Project Instructions

## Working agreement

You are implementing LogScope from `SPEC.md`.

Follow the specification exactly. If requirements conflict or important information is missing, stop and ask before making a significant assumption.

## Mandatory workflow

1. Inspect the repository, `SPEC.md`, and `sample.log` before planning.
2. Do not write implementation code until you have produced an implementation plan and the user has approved or edited it.
3. Implement in this exact sequence:
   1. parser and parser tests
   2. summary command and tests
   3. timeline command and tests
   4. grep command and tests
   5. JSON and Markdown output support and tests
   6. synthetic log generator, benchmark, documentation, and final verification
4. After each step:
   - run the relevant test suite;
   - fix failures;
   - show a concise summary of changed files and test results;
   - wait for approval before committing;
   - commit only after approval, using the requested commit message.
5. Never make one large “everything” commit.
6. Use streaming file processing. Never use a full-file read API for log input.
7. Treat malformed lines as data quality issues: count and skip them, never crash.
8. Keep stdout clean for machine-readable JSON. Send errors and diagnostics to stderr.
9. Do not add an LLM integration unless the required implementation is complete and the user explicitly asks for the stretch goal.
10. Do not commit generated 100 MB logs, Markdown reports, virtual environments, package directories, or secrets.

## Planning requirements

The plan must include:

- selected language and rationale;
- proposed project structure;
- parser grammar based on the actual `sample.log`;
- data model;
- streaming and memory strategy;
- CLI library choice;
- output/report design;
- test strategy;
- benchmark strategy;
- exact incremental commit plan;
- risks or assumptions needing confirmation.

## Code quality requirements

- Prefer standard-library dependencies unless a third-party package materially improves reliability.
- Write focused unit tests as each feature is added.
- Use clear error messages and non-zero exit codes for invalid CLI input or unreadable files.
- Preserve raw matched lines for `grep` where possible.
- Ensure Markdown output writes a file and prints only the report path on success.
- Update `README.md` as functionality is added.
- Add or update `.gitignore` before generating large benchmark data.

## Definition of done

Do not claim completion until all of the following have been verified:

- all three required commands run successfully on `sample.log`;
- parser and command tests pass;
- malformed-line count is reported;
- JSON and Markdown formats work for every command;
- a 100 MB synthetic log is processed in under 60 seconds;
- memory remains stable and the measurement approach is documented;
- `BENCHMARK.md`, `README.md`, and `.gitignore` are complete;
- Git history shows a separate plan commit followed by incremental feature commits.
