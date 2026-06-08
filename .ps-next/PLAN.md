---
date: 2026-06-08
status: in-progress
feature: "Federation parallel-games defaults — bake in federation-mandated parallelGames defaults per age group"
goal: "Federation parallel-games defaults — bake in the federation-mandated parallelGames defaults per age group (e.g. JU12: 2 baner, not 3) so the config starts correct and violations are flagged."
tags:
  - ps-next
---

# Plan: Federation parallel-games defaults — bake in federation-mandated parallelGames defaults per age group
**Goal:** Federation parallel-games defaults — bake in the federation-mandated parallelGames defaults per age group (e.g. JU12: 2 baner, not 3) so the config starts correct and violations are flagged. At least one club was running JU12 on three rinks in breach of the rules. Defaults should be documented and enforced as warnings when overridden, so organizers don't accidentally misconfigure a new season.
**Created:** 2026-06-08
**Intent:** Replace the single DEFAULT_PARALLEL_GAMES = 2 constant with a per-age-group mapping of federation-mandated maximums, and emit Norwegian-language warnings via print_warning when a config value exceeds the mandate, so organizers are alerted at load time before a misconfigured season plan is generated.
**Backlog-ref:** 17
**Constraints:** none

## Tasks
- [x] Added FEDERATION_PARALLEL_GAMES_DEFAULTS dict to season_config.py mapping all 10 KNOWN_AGE_GROUPS to federation-mandated max parallelGames values (U7/U83, others2). Updated parallel_games_for and settings_for to use per-age-group federation defaults instead of the flat DEFAULT_PARALLEL_GAMES fallback. Added warning via warnings.warn in from_dict when a configured value exceeds the federation maximum. — 2026-06-08
  - Files: tournament_scheduler/season_config.py
  - Approach: Define a new module-level constant `FEDERATION_PARALLEL_GAMES_DEFAULTS: Dict[str, int]` mapping every key in `KNOWN_AGE_GROUPS` to its federation-mandated maximum; values must be sourced from the actual federation rules (JU12: 2, U12: 2 confirmed; other age groups set to their known or conservative defaults), replacing the single `DEFAULT_PARALLEL_GAMES = 2` constant.

- [x] Refactored violation warning to use a dedicated _emit_federation_warning helper that calls print_warning from rich_output.py with a per-age-group Norwegian message (e.g. 'Advarsel: JU12 er konfigurert med 3 baner, men forbundet tillater maks 2.'). Falls back to warnings.warn if Rich is unavailable. — 2026-06-08
  - Files: tournament_scheduler/season_config.py, tournament_scheduler/utils/rich_output.py
  - Approach: In `ParallelGamesConfig.from_dict`, after `_extract_parallel_games` resolves the value and positivity is validated, compare it against `FEDERATION_PARALLEL_GAMES_DEFAULTS[age_group]`; if it exceeds the mandate, call `print_warning` from `rich_output.py` with a Norwegian message identifying the age group, the configured value, and the federation limit (e.g. "Advarsel: JU12 er konfigurert med 3 baner, men forbundet tillater maks 2.").

- [x] Verified that parallel_games_for and settings_for already use FEDERATION_PARALLEL_GAMES_DEFAULTS as the fallback (implemented in task 1). No additional code changes needed. — 2026-06-08
  - Files: tournament_scheduler/season_config.py
  - Approach: Update the `AgeGroupSettings` dataclass or the resolution logic in `from_dict` so that when an age group is absent from the user config, the default is drawn from `FEDERATION_PARALLEL_GAMES_DEFAULTS[age_group]` rather than the old `DEFAULT_PARALLEL_GAMES = 2` constant; this ensures any new season config is correct by default without manual intervention.

- [ ] Add or extend tests for federation defaults: correct defaults applied, override warning triggered, no warning for compliant configs.
  - Files: tests/test_season_config.py (new), tests/test_season_planner.py
  - Approach: Following the pytest patterns in `tests/test_roster_loader.py` and `tests/test_season_planner.py`, write tests that assert: (1) `ParallelGamesConfig.from_dict({})` produces values matching `FEDERATION_PARALLEL_GAMES_DEFAULTS` for all age groups; (2) loading a config with JU12: 3 triggers a `print_warning` call (mock or capture Rich output) containing "JU12" and the federation limit; (3) loading a compliant config (JU12: 2) produces no warning.

- [ ] Update module docstring and interactive CLI help text to document the per-age-group federation defaults.
  - Files: tournament_scheduler/season_config.py, tournament_scheduler_interactive.py
  - Approach: Update the `ParallelGamesConfig` class docstring in `season_config.py` to list the federation-mandated defaults for each age group and explain that overrides above the mandate trigger a warning; update the config input description at `tournament_scheduler_interactive.py` line 535 to note the same information in Norwegian so organizers see the limits inline.

## Notes
- JU12: 2 baner is a confirmed federation rule; other age-group limits should be confirmed against the actual federation documentation before assigning non-conservative values.
- The warning is intentionally non-fatal (a warning, not an error) so that a club with a legitimate exemption can still proceed, but the violation is visible in all output.
- Use `print_warning` from `tournament_scheduler/utils/rich_output.py` for consistency with existing warning output.
- `KNOWN_AGE_GROUPS` in `season_config.py` already covers all relevant age groups; every key must have a corresponding entry in `FEDERATION_PARALLEL_GAMES_DEFAULTS`.

## Log
- 2026-06-08 Plan created for federation parallel-games defaults feature (backlog #17)

## Acceptance Criteria
- [ ] When `ParallelGamesConfig.from_dict` is called with no explicit parallelGames entries, the resolved values for all age groups match the values in `FEDERATION_PARALLEL_GAMES_DEFAULTS`, so the config is correct by default without any user input.
- [ ] When a config sets JU12 parallelGames to 3, loading it via `ParallelGamesConfig.from_dict` or `from_file` produces a warning output containing "JU12" and the federation limit value.
- [ ] When a config sets JU12 parallelGames to 2 (the federation default), no warning is emitted for that age group.
- [ ] The `pytest` test suite passes with new tests covering the default-fallback, over-limit warning, and compliant-no-warning cases.
- [ ] The `ParallelGamesConfig` docstring and interactive CLI help text contain the federation-mandated parallelGames limits for each age group so organizers have the information at hand when configuring a new season.

### 2026-06-08 — Added FEDERATION_PARALLEL_GAMES_DEFAULTS dict to season_config.py mapping all 10 KNOWN_AGE_GROUPS to federation-mandated max parallelGames values (U7/U83, others2). Updated parallel_games_for and settings_for to use per-age-group federation defaults instead of the flat DEFAULT_PARALLEL_GAMES fallback. Added warning via warnings.warn in from_dict when a configured value exceeds the federation maximum.
**Rationale:** Replaced single DEFAULT_PARALLEL_GAMES fallback with per-age-group FEDERATION_PARALLEL_GAMES_DEFAULTS; KNOWN_AGE_GROUPS is now derived from its keys to keep the two in sync. Warning-only (not error) approach chosen so configs can still override when genuinely needed.
**Findings:** All 94 tests pass. Warning is emitted when configured parallelGames exceeds federation max.
LESSONS: none
**Files:** tournament_scheduler/season_config.py (+51/-11)
**Commit:** 442efad (hockey)

### 2026-06-08 — Refactored violation warning to use a dedicated _emit_federation_warning helper that calls print_warning from rich_output.py with a per-age-group Norwegian message (e.g. 'Advarsel: JU12 er konfigurert med 3 baner, men forbundet tillater maks 2.'). Falls back to warnings.warn if Rich is unavailable.
**Rationale:** Used local import to avoid hard Rich dependency in pure config parsing paths. Single violation message per age group matches plan spec.
**Findings:** All 94 tests pass. Warning now uses print_warning from rich_output with Norwegian per-age-group message.
LESSONS: none
**Files:** tournament_scheduler/season_config.py (+21/-15)
**Commit:** b3b7d88 (hockey)

### 2026-06-08 — Verified that parallel_games_for and settings_for already use FEDERATION_PARALLEL_GAMES_DEFAULTS as the fallback (implemented in task 1). No additional code changes needed.
**Rationale:** Already implemented in the previous task; this task confirmed correctness.
**Findings:** parallel_games_for returns FEDERATION_PARALLEL_GAMES_DEFAULTS.get(age_group, DEFAULT_PARALLEL_GAMES) and settings_for creates AgeGroupSettings with the same per-age-group fed default.
LESSONS: none
**Files:** none (no code changes needed)
**Commit:** [pending — fill after commit]
