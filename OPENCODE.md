## RVV Miniputt skill
When working with scraping, calendar generation, season planning, or pipeline debugging, use the RVV skill in `.agents/skills/rvv/SKILL.md`.

## Slash commands — execute directly
When the user types `/rvv-miniputt run`, `/rvv-miniputt status`, `/rvv-miniputt logs`, `/rvv-miniputt guide`, `/rvv-miniputt calendars`, or any other registered slash command, execute it immediately via the extension handler. Do not investigate, verify, or inspect the command first — the extension handles everything. Just run it.

These slash commands are Pi extension commands, NOT shell binaries — never run them via shell (`/rvv-miniputt run` will fail with "command not found"). Outside Pi or when you need a harness-neutral entrypoint, use `scripts/rvv-miniputt ...` or `python3 -m tournament_scheduler.cli.rvv_cli ...` as documented in `.agents/skills/rvv/SKILL.md`.

When planning or changing scheduling logic, always review whether the rules report and related docs need to be updated to match the new behavior.
