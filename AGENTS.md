<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

## Slash commands — execute directly
When the user types `/rvv-miniputt run`, `/rvv-miniputt status`, `/rvv-miniputt logs`, `/rvv-miniputt guide`, `/rvv-miniputt calendars`, or any other registered slash command, execute it immediately via the extension handler. Do not investigate, verify, or inspect the command first — the extension handles everything. Just run it.

These slash commands are Pi extension commands, NOT shell binaries — never run them via the Bash tool (`/rvv-miniputt run` will fail with "command not found"). If you (the agent) need to trigger the RVV Miniputt pipeline yourself rather than waiting for the user to type the slash command, call the corresponding tool instead: `rvv_miniputt_run`, `rvv_miniputt_status`, `rvv_miniputt_logs`, `rvv_miniputt_calendars`. Never reimplement the pipeline by calling `tournament_scheduler.pipeline.stageN_*` Python modules directly — that skips checkpointing, resumption, and structured run logging.