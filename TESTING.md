# Actual validation

Builder environment: Windows, Python 3.11.15, 2026-11-03. Commands were run from the repository root. Hosted Ubuntu/Windows validation is handled separately by the release controller; these local results do not claim hosted CI success.

```console
python -m unittest discover -s tests -v
```

Latest local run: **32 tests passed in 7.318 seconds**. Subprocess invocations use the current interpreter, source basename, repository-root cwd and a 10-second timeout. Test-created inputs live in temporary directories.

Coverage includes exact threshold and decimal boundary comparisons; mixed violations and unknowns; -1 body sentinel; forbidden negative time; ignored content.size; huge and tiny finite values; numeric overflow and 128-character cap; strict duplicate keys, surrogate pairs, malformed UTF-8/JSON; nesting boundary, byte/node/entry limits; privacy on valid and malformed input; unchanged input hashes and no extra input-directory files; neutral argument/file errors; URI/UNC/mixed/device refusal before mocked stat/open; and actual OS pipes closed before process startup, including help.

Actual development evidence is retained outside the publishable repository in the batch's `builder-evidence/har-entry-budget/` directory:

- `red.log`: before source implementation, 29 tests / 40 failing assertions because the tool was absent.
- `green-1.log`: initial implementation, 29 tests passing.
- `red-boundary.log`: two additional boundary probes, 31 tests passing; this probe did **not** expose a failure and is not claimed as RED evidence.
- `red-range.log`: 32 tests with one expected failure: a value just above the supported finite magnitude was incorrectly accepted due to context rounding during absolute-value computation.
- `green-final.log`: exact nonrounding absolute-value fix, 32 tests passing.

The committed synthetic examples and fixtures also define four controller smoke cases in `checks.json` covering clean 0, findings 1, negative time 2 and duplicate JSON keys 2. All examples are source files; no installed entrypoint is required.

Limits and threat boundaries are documented in README. Tests do not certify network-local backing of symlinks/mounts, absence of filesystem races, full HAR compliance, or privacy of the original archive.
