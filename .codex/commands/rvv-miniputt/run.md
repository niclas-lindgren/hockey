Run the RVV Miniputt pipeline from this repository.

Rules:
- Never run `/rvv-miniputt ...` as a shell command.
- Use `scripts/rvv-miniputt run <user-args>`.
- If that fails because the launcher is unavailable, retry with `python3 -m tournament_scheduler.cli.rvv_cli run <user-args>`.
- Report the actual command used and summarize the result.
- Do not reimplement the pipeline by calling `tournament_scheduler.pipeline.stageN_*` modules directly.
