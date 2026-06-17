---
name: "RVV Miniputt: Run"
description: "Run the RVV Miniputt pipeline from Claude using the repo-local launcher"
category: RVV
---

Run the RVV Miniputt pipeline from this repository.

## Rules

- Never run `/rvv-miniputt ...` as a shell command.
- Use the harness-neutral repo entrypoint instead:

```bash
scripts/rvv-miniputt run <user-args>
```

- If `scripts/rvv-miniputt` fails because the virtualenv is missing or broken, retry with:

```bash
python3 -m tournament_scheduler.cli.rvv_cli run <user-args>
```

- Report the actual command used and summarize the result.
- Keep the response concise, but include actionable failures.
- Do not reimplement the pipeline by calling `tournament_scheduler.pipeline.stageN_*` modules directly.

## Examples

- `/rvv-miniputt:run`
- `/rvv-miniputt:run --resume-from 2 --log-level verbose`
