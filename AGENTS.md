## RVV Miniputt command surface
In Pi, `/rvv-miniputt ...` is provided by the Pi extension handler and should be executed directly there.

Outside Pi, do not assume that `/rvv-miniputt ...` exists as a native slash command. Use the harness-local adapters when present (`.claude/commands/rvv-miniputt/`, `.opencode/commands/rvv-miniputt/`, `.codex/commands/rvv-miniputt/`) or the harness-neutral repo entrypoints: `scripts/rvv-miniputt ...` and `python3 -m tournament_scheduler.cli.rvv_cli ...`.

These Pi slash commands are NOT shell binaries — never run `/rvv-miniputt ...` via the Bash tool (`/rvv-miniputt run` will fail with `command not found`). If you (the agent) need to trigger the RVV Miniputt pipeline yourself inside Pi rather than waiting for the user to type the slash command, call the corresponding tool instead: `rvv_miniputt_run`, `rvv_miniputt_status`, `rvv_miniputt_logs`, `rvv_miniputt_calendars`. Never reimplement the pipeline by calling `tournament_scheduler.pipeline.stageN_*` Python modules directly — that skips checkpointing, resumption, and structured run logging.

When planning or changing scheduling logic, always review whether the rules report and related docs need to be updated to match the new behavior.
