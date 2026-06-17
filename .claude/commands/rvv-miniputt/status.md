---
name: "RVV Miniputt: Status"
description: "Show RVV Miniputt pipeline stage status from Claude"
category: RVV
---

Show the current RVV Miniputt pipeline status.

Use:

```bash
scripts/rvv-miniputt status <user-args>
```

Fallback if needed:

```bash
python3 -m tournament_scheduler.cli.rvv_cli status <user-args>
```

Never run `/rvv-miniputt status` in the shell. Report the status concisely.
