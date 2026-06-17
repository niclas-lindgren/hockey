## RVV Miniputt skill
When working with scraping, calendar generation, season planning, or pipeline debugging, use the RVV skill in `.agents/skills/rvv/SKILL.md`.

## RVV Miniputt commands in Claude
Claude does not load Pi extensions directly. In this repo, use the Claude project commands under `.claude/commands/rvv-miniputt/`:

- `/rvv-miniputt:run`
- `/rvv-miniputt:status`
- `/rvv-miniputt:logs`
- `/rvv-miniputt:calendars`
- `/rvv-miniputt:guide`

These commands should execute the repo-local launcher, not the Pi slash command. Never run `/rvv-miniputt ...` via shell (`/rvv-miniputt run` will fail with `command not found`). The harness-neutral entrypoints are `scripts/rvv-miniputt ...` and `python3 -m tournament_scheduler.cli.rvv_cli ...`, as documented in `.agents/skills/rvv/SKILL.md`.

When planning or changing scheduling logic, always review whether the rules report and related docs need to be updated to match the new behavior.
