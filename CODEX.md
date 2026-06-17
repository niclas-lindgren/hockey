# CODEX.md

## RVV Miniputt

When working with scraping, calendar generation, season planning, or pipeline debugging, use the RVV skill in `.agents/skills/rvv/SKILL.md`.

### Command equivalents

Pi exposes `/rvv-miniputt ...` as native extension slash commands.
Codex should use the harness-neutral repo entrypoints instead:

```bash
scripts/rvv-miniputt run
scripts/rvv-miniputt status
scripts/rvv-miniputt logs list
scripts/rvv-miniputt calendars
# or
python3 -m tournament_scheduler.cli.rvv_cli <subcommand>
```

Rules:
- Never run `/rvv-miniputt ...` as a shell command.
- Never reimplement the pipeline by calling `tournament_scheduler.pipeline.stageN_*` modules directly.
- When planning or changing scheduling logic, review whether the rules report and related docs must be updated.

### Cross-harness boundary

- Pi-only: native `/rvv-miniputt ...` slash commands, `/rvv-miniputt guide`, live progress notifications, and agent-callable `rvv_miniputt_*` tools.
- Codex/OpenCode/Claude: use `scripts/rvv-miniputt ...` or `python3 -m tournament_scheduler.cli.rvv_cli ...`.
