# Build History

One entry per archived feature. For full Goal / Tasks / Rationale / Files / Commits, open the linked ARCHIVED/PLAN-*.md.

- 2026-06-08: Manual roster config loader — add a YAML/JSON config format listing each club and its teams (supports multiple teams per club, e.g. "Jar 1", "Jar 2"), with validation and clear Norwegian-language error messages on malformed entries, loaded by both CLI and interactive entry points.; plan: ARCHIVED/PLAN-2
- 2026-06-08: Federation parallel-games defaults — bake in the federation-mandated parallelGames defaults per age group (e.g. JU12: 2 baner, not 3) so the config starts correct and violations are flagged. At least one club was running JU12 on three rinks in breach of the rules. Defaults should be documented and enfor
- 2026-06-09: Agentic season-planning pipeline — restructure the tool as a four-stage pipeline where each stage has an LLM quality gate before the next stage runs. Stage 1 (Config): parse and validate input.json — teams, clubs, age groups, date range, parallel-games config — and surface clear Norwegian-language e
- 2026-06-09: Support modifying specific tournaments after the season plan is generated — drop a team from a tournament (rebalancing round-robin games) and move a tournament to a different weekend (with conflict re-checking and cascade handling).; plan: ARCHIVED/PLAN-2026-06-09-tournament-update-and-rescheduling.md; built tournament_scheduler/models.py (+1/-1), tournament_scheduler/pipeline/stage3_planning.py (+39)
