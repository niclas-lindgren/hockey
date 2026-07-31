## Engineering philosophy

This is a volunteer-maintained hobby project with low traffic, limited usage, and limited maintainer time. Prefer pragmatic, boring solutions that are easy to understand, operate, and hand over.

When proposing architecture or implementing changes:

- Choose the simplest solution that satisfies the current requirements.
- Minimize dependencies, services, infrastructure, credentials, and operational steps.
- Prefer existing repository scripts, GitHub Actions, Power Automate, SharePoint, Microsoft Forms, and other already-used tools over adding custom infrastructure.
- Optimize for readability, deterministic behavior, easy debugging, and volunteer maintainability rather than theoretical scale or enterprise completeness.
- Avoid microservices, queues, custom authentication services, GitHub Apps, cloud functions, Kubernetes, and similar infrastructure unless a demonstrated requirement makes the simpler approach insufficient.
- Do not add abstraction, extensibility, or scalability for hypothetical future needs.
- Prefer a narrowly scoped fine-grained PAT over a custom token service when repository automation only needs limited access to one repository.
- Explain material trade-offs, but recommend the proportionate solution for a small volunteer-run system by default.

Assume a handful of maintainers, tens or hundreds of users, infrequent updates, low traffic, and no dedicated operations team unless the repository clearly shows otherwise.

## RVV Miniputt command surface
In Pi, `/rvv-miniputt ...` is provided by the Pi extension handler and should be executed directly there.

Outside Pi, do not assume that `/rvv-miniputt ...` exists as a native slash command. Use the harness-local adapters when present (`.claude/commands/rvv-miniputt/`, `.opencode/commands/rvv-miniputt/`, `.codex/commands/rvv-miniputt/`) or the harness-neutral repo entrypoints: `scripts/rvv-miniputt ...` and `python3 -m tournament_scheduler.cli.rvv_cli ...`.

These Pi slash commands are NOT shell binaries — never run `/rvv-miniputt ...` via the Bash tool (`/rvv-miniputt run` will fail with `command not found`). If you (the agent) need to trigger the RVV Miniputt pipeline yourself inside Pi rather than waiting for the user to type the slash command, call the corresponding tool instead: `rvv_miniputt_run`, `rvv_miniputt_publish`, `rvv_miniputt_status`, `rvv_miniputt_logs`, `rvv_miniputt_calendars`. Never reimplement the pipeline by calling `tournament_scheduler.pipeline.stageN_*` Python modules directly — that skips checkpointing, resumption, and structured run logging.

When planning or changing scheduling logic, always review whether the rules report and related docs need to be updated to match the new behavior.
