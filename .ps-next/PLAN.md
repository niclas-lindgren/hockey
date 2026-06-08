---
date: 2026-06-08
status: in-progress
feature: "Manual roster config loader — YAML/JSON club/team config with Norwegian-language validation"
goal: "Manual roster config loader — add a YAML/JSON config format listing each club and its teams (supports multiple teams per club, e.g. \"Jar 1\", \"Jar 2\"), with validation and clear Norwegian-language error messages on malformed entries, loaded by both CLI and interactive entry points."
tags:
  - ps-next
---

# Plan: Manual roster config loader — YAML/JSON club/team config with Norwegian-language validation
**Goal:** Manual roster config loader — add a YAML/JSON config format listing each club and its teams (supports multiple teams per club, e.g. "Jar 1", "Jar 2"), with validation and clear Norwegian-language error messages on malformed entries, loaded by both CLI and interactive entry points.
**Created:** 2026-06-08
**Intent:** Replace the bare-bones, English-language, JSON-only RosterLoader stub with a robust YAML/JSON loader that mirrors the project's existing ParallelGamesConfig pattern (Norwegian validation errors, optional YAML support), and wire it into both the scriptable CLI and the interactive Norwegian-language flow so organizers can prepare a season roster file once and reuse it everywhere.
**Backlog-ref:** 2

## Tasks
- [x] Rewrote RosterLoader with from_file/from_dict classmethods mirroring ParallelGamesConfig, supporting JSON+YAML and raising RosterConfigError with thorough Norwegian-language validation messages; updated season_command.py to catch the new exception type. — 2026-06-08
  - Files: tournament_scheduler/roster_loader.py, tournament_scheduler/season_config.py
  - Approach: Replace the current `RosterLoader.load()` (sys.exit/print-based, JSON-only, English messages) with `RosterLoader.from_file(path)` / `from_dict(data)` classmethods that mirror `ParallelGamesConfig.from_file`/`from_dict` in season_config.py — reading `.yaml`/`.yml` via the optional `pyyaml` import (with the same `_YAML_AVAILABLE` Norwegian fallback message: "pakken 'pyyaml' er ikke installert ...") and `.json` via `json.loads`, raising a shared/reusable exception (either reuse `SeasonConfigError` from season_config.py or add a `RosterConfigError(ValueError)` alongside it) with Norwegian messages for: file not found, unparseable JSON/YAML, wrong top-level shape (expected club -> {team label: age group} mapping), empty club entries (a club listed with no teams), duplicate team labels within or across clubs, missing/blank labels, and unknown age groups (validate against `KNOWN_AGE_GROUPS` from season_config.py). Keep the existing dict-of-clubs format (`{"Jar": {"Jar 1": "U10", "Jar 2": "U11"}}`) as the canonical shape supporting multiple teams per club; drop or clearly deprecate the flat-list format to keep one canonical shape consistent with `ParallelGamesConfig`'s structure.

- [x] Verified that season_command.py already calls RosterLoader.from_file(args.roster_file) wrapped in try/except RosterConfigError, rendering errors via TournamentOutput.print_error and sys.exit(1) — this was completed as part of the prior RosterLoader rewrite task. — 2026-06-08
  - Files: tournament_scheduler/cli/season_command.py
  - Approach: Replace the `RosterLoader.load(args.roster_file)` call at season_command.py:28 with `RosterLoader.from_file(args.roster_file)` wrapped in `try/except` for the new error type, following the exact pattern already used for `ParallelGamesConfig.from_file` in `_load_parallel_games_config` (season_command.py:82-92) — catch the exception, render the Norwegian message via `TournamentOutput.print_error(str(exc))`, and `sys.exit(1)`.

- [x] Extended collect_roster_entries() in the interactive CLI to first prompt for an optional YAML/JSON roster config file path; on entry it calls RosterLoader.from_file, prints Norwegian RosterConfigError messages and lets the user retry or fall back to manual entry, and falls through to the existing manual line-by-line loop unchanged when left blank. — 2026-06-08
  - Files: tournament_scheduler_interactive.py
  - Approach: Extend `collect_roster_entries()` (tournament_scheduler_interactive.py:437-479) to first ask the user (in Norwegian, via the existing `ask_text`/menu-prompt helpers) whether to load the roster from a YAML/JSON config file or enter teams manually; when a file path is given, call `RosterLoader.from_file(path)`, catch the new exception type, print the Norwegian validation error via the existing `print(...)` console conventions used elsewhere in this function, and let the user retry or fall back to manual entry; when left blank, fall through to the existing manual line-by-line entry loop unchanged. Update `collect_season_plan_params()` (lines 482-516) only if needed to thread the chosen roster source through.

- [x] Confirmed RosterLoader already imports _YAML_AVAILABLE and yaml directly from season_config.py (single source of truth, no duplication) from the prior rewrite; added a commented optional pyyaml>6.0 dependency note to requirements.txt documenting that both ParallelGamesConfig and RosterLoader support optional YAML loading with a Norwegian fallback message. — 2026-06-08
  - Files: tournament_scheduler/season_config.py, tournament_scheduler/roster_loader.py, requirements.txt
  - Approach: Factor the `try: import yaml ... _YAML_AVAILABLE` block in season_config.py into a small shared helper (or import it directly from season_config.py into roster_loader.py) so both `ParallelGamesConfig` and `RosterLoader` use one source of truth for YAML availability and the Norwegian "pyyaml ikke installert" message; add `pyyaml` as an optional/commented dependency note in requirements.txt (matching how the project already documents optional YAML support for `ParallelGamesConfig` per season_config.py's module docstring) so both loaders behave identically whether or not `pyyaml` is present.

- [ ] Write tests covering the new roster config loader's parsing, validation, and Norwegian error messages
  - Files: tests/test_roster_loader.py (new)
  - Approach: Following the pytest conventions used in tests/test_season_planner.py and the validation-error tests implied by season_config.py, write tests that: (1) load a valid JSON roster config with multiple clubs and multiple teams per club (e.g. "Jar 1"/"Jar 2") and assert the resulting `Roster`/`Team` objects match; (2) load an equivalent valid YAML config (skip/xfail gracefully if `pyyaml` is unavailable, mirroring how season_config.py documents optional YAML); (3) assert that malformed inputs — missing file, unparseable JSON/YAML, wrong top-level shape, empty club team-maps, duplicate team labels, unknown age groups, blank labels — each raise the loader's exception with a Norwegian-language message containing the offending value; (4) assert `RosterLoader.from_file` and `RosterLoader.from_dict` produce identical `Roster` objects for equivalent JSON/YAML inputs.

- [ ] Update module docstrings and in-CLI help/prompt text to document the new roster config file format and both loading paths
  - Files: tournament_scheduler/roster_loader.py, tournament_scheduler.py, tournament_scheduler_interactive.py
  - Approach: Update the `RosterLoader` module docstring (roster_loader.py:1-26) to describe the canonical YAML/JSON club→teams shape (mirroring `ParallelGamesConfig`'s docstring style in season_config.py), document that multiple teams per club are supported (e.g. "Jar 1", "Jar 2"), and that malformed entries raise Norwegian-language errors; update the `--roster-file` argparse help text in tournament_scheduler.py to mention YAML/JSON support; update the interactive prompt text added in the previous task to briefly explain the expected file format to the user in Norwegian.

## Notes
- The existing `RosterLoader.load()` uses `print(..., file=sys.stderr)` + `sys.exit(1)` directly — this plan replaces that with the project's established exception-based pattern (`SeasonConfigError`/`ValueError` subclass with Norwegian messages), matching `ParallelGamesConfig` in season_config.py, so callers (CLI and interactive) can catch and render errors consistently via `TournamentOutput.print_error`.
- `KNOWN_AGE_GROUPS` already exists in season_config.py — reuse it rather than duplicating the set of valid age groups.
- The canonical roster config shape is the dict-of-clubs form (`{"Jar": {"Jar 1": "U10", "Jar 2": "U11"}}`), which already naturally supports multiple teams per club and mirrors `ParallelGamesConfig`'s structure per PROJECT.md's "additional requirements" section.
- `pyyaml` is optional — both loaders must degrade gracefully with a clear Norwegian error when a `.yaml`/`.yml` file is requested but the package isn't installed, exactly as `ParallelGamesConfig.from_file` already does.
- Findings above come from direct inspection of tournament_scheduler/roster_loader.py, season_config.py, models.py, cli/season_command.py, and tournament_scheduler_interactive.py (collect_roster_entries/run_season_plan/collect_season_plan_params), plus the archived plan ARCHIVED/PLAN-2026-06-08-full-season-tournament-schedule-generato.md which established the `ParallelGamesConfig` Norwegian-error/JSON+YAML pattern this plan mirrors.

## Acceptance Criteria
- [ ] Loading a valid YAML or JSON roster config file (with multiple clubs and multiple teams per club, e.g. "Jar 1" and "Jar 2" both under "Jar") via `RosterLoader.from_file` returns a `Roster` whose `Team` objects match the club/label/age-group entries in the file.
- [ ] Loading a malformed roster config (unknown age group, duplicate team label, empty club entry, or unparseable YAML/JSON) causes `RosterLoader.from_file` to raise an exception whose Norwegian-language message contains the specific offending value.
- [ ] Running `tournament_scheduler.py --generate-season --roster-file <malformed-file>` exits with a non-zero status code and prints a Norwegian-language error describing the validation failure, matching the existing `ParallelGamesConfig` error-handling pattern in `cli/season_command.py`.
- [ ] The interactive flow's roster collection (`collect_roster_entries`) offers the user a choice to load teams from a YAML/JSON config file, and on a malformed file it prints the same Norwegian-language validation error and lets the user retry or fall back to manual entry rather than crashing.
- [ ] Running `pytest tests/test_roster_loader.py` exits with code 0, confirming the loader correctly parses valid JSON/YAML roster configs into matching `Roster`/`Team` objects and raises Norwegian-language errors for each class of malformed input.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-08 — Rewrote RosterLoader with from_file/from_dict classmethods mirroring ParallelGamesConfig, supporting JSON+YAML and raising RosterConfigError with thorough Norwegian-language validation messages; updated season_command.py to catch the new exception type.
**Rationale:** Mirrored ParallelGamesConfig.from_file/from_dict pattern exactly (reusing _YAML_AVAILABLE/yaml/KNOWN_AGE_GROUPS from season_config.py) for consistency; dropped the flat-list format to keep one canonical club->{label:age_group} shape.
**Findings:** All 45 existing tests pass; no test files reference RosterLoader directly so no test updates were needed; only one call site existed (season_command.py).
LESSONS: RosterLoader.load(path) was replaced entirely by RosterLoader.from_file(path)/from_dict(data) raising RosterConfigError(ValueError) with Norwegian messages — any future caller must use try/except RosterConfigError + TournamentOutput.print_error, matching _load_parallel_games_config's pattern.
**Files:** tournament_scheduler/roster_loader.py (+~140/-~40), tournament_scheduler/cli/season_command.py (+8/-1)
**Commit:** 9db38fa (hockey)

### 2026-06-08 — Verified that season_command.py already calls RosterLoader.from_file(args.roster_file) wrapped in try/except RosterConfigError, rendering errors via TournamentOutput.print_error and sys.exit(1) — this was completed as part of the prior RosterLoader rewrite task.
**Rationale:** This task's required change was implemented inline while rewriting RosterLoader (same call site, same commit scope was natural to do together); no separate edit was needed.
**Findings:** Confirmed via grep that line 28-32 of season_command.py uses RosterLoader.from_file with the exact try/except + print_error + sys.exit(1) pattern matching _load_parallel_games_config; no further changes required.
LESSONS: When a plan splits 'rewrite X' and 'update caller of X' into separate tasks, the rewrite task may naturally include updating the (sole) caller — check git history/diff before assuming a separate edit is needed.
**Files:** none (no files changed — already implemented in commit 9db38fa)
**Commit:** 0956879 (hockey)

### 2026-06-08 — Extended collect_roster_entries() in the interactive CLI to first prompt for an optional YAML/JSON roster config file path; on entry it calls RosterLoader.from_file, prints Norwegian RosterConfigError messages and lets the user retry or fall back to manual entry, and falls through to the existing manual line-by-line loop unchanged when left blank.
**Rationale:** Kept the existing manual-entry loop entirely intact and added the file-load path as an opt-in prompt before it, matching the function's existing print()-based Norwegian console conventions and the retry/fallback UX pattern; reused RosterLoader.from_file/RosterConfigError from the prior rewrite rather than duplicating loading logic.
**Findings:** All 45 tests still pass; py_compile confirms no syntax errors; collect_season_plan_params() needed no changes since it already just calls collect_roster_entries() and uses the returned Roster directly.
LESSONS: collect_roster_entries() prints via plain print() (not Rich/TournamentOutput) — match that convention for any further interactive-flow roster UX changes; RosterConfigError messages are already Norwegian and can be printed directly with no extra wrapping.
**Files:** tournament_scheduler_interactive.py (+28/-0)
**Commit:** f6a433a (hockey)

### 2026-06-08 — Confirmed RosterLoader already imports _YAML_AVAILABLE and yaml directly from season_config.py (single source of truth, no duplication) from the prior rewrite; added a commented optional pyyaml>6.0 dependency note to requirements.txt documenting that both ParallelGamesConfig and RosterLoader support optional YAML loading with a Norwegian fallback message.
**Rationale:** Importing _YAML_AVAILABLE/yaml directly from season_config.py (done during the RosterLoader rewrite) avoids duplicating the try/import block and guarantees identical behavior; documented as a commented-out optional dependency in requirements.txt to match how the project keeps Playwright etc. pinned while noting optional extras.
**Findings:** All 45 tests pass;  confirms the cross-module import of the private _YAML_AVAILABLE/yaml symbols works at runtime.
LESSONS: RosterLoader shares _YAML_AVAILABLE and yaml by importing them directly from season_config.py rather than re-implementing the try/except import block — keep this single source of truth if either loader's YAML handling changes.
**Files:** requirements.txt (+7/-0)
**Commit:** [pending — fill after commit]
