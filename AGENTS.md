# Agent instructions

Read and follow these tool-neutral project documents before proposing architecture or implementing changes:

- [`docs/engineering-principles.md`](docs/engineering-principles.md)
- [`docs/system-architecture.md`](docs/system-architecture.md)

## RVV Miniputt command surface

In Pi, `/rvv-miniputt ...` is provided by the Pi extension handler and should be executed directly there.

Outside Pi, do not assume that `/rvv-miniputt ...` exists as a native slash command. Use the harness-local adapters when present (`.claude/commands/rvv-miniputt/`, `.opencode/commands/rvv-miniputt/`, `.codex/commands/rvv-miniputt/`) or the harness-neutral repository entrypoints:

- `scripts/rvv-miniputt ...`
- `python3 -m tournament_scheduler.cli.rvv_cli ...`

Pi slash commands are not shell binaries. Never run `/rvv-miniputt ...` through a shell.

When operating inside Pi, use the corresponding tools rather than reimplementing the pipeline:

- `rvv_miniputt_run`
- `rvv_miniputt_publish`
- `rvv_miniputt_status`
- `rvv_miniputt_logs`
- `rvv_miniputt_calendars`

Do not call `tournament_scheduler.pipeline.stageN_*` modules directly when that bypasses checkpointing, resumption, or structured run logging.

When planning or changing scheduling logic, review whether the rules report and related documentation must be updated to match the new behavior.
