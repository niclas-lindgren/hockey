# Build History

One entry per archived feature. For full Goal / Tasks / Rationale / Files / Commits, open the linked ARCHIVED/PLAN-*.md.

- 2026-06-08: Manual roster config loader — add a YAML/JSON config format listing each club and its teams (supports multiple teams per club, e.g. "Jar 1", "Jar 2"), with validation and clear Norwegian-language error messages on malformed entries, loaded by both CLI and interactive entry points.; plan: ARCHIVED/PLAN-2
- 2026-06-08: Federation parallel-games defaults — bake in the federation-mandated parallelGames defaults per age group (e.g. JU12: 2 baner, not 3) so the config starts correct and violations are flagged. At least one club was running JU12 on three rinks in breach of the rules. Defaults should be documented and enfor
