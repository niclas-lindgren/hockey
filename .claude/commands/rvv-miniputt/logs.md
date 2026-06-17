---
name: "RVV Miniputt: Logs"
description: "Inspect RVV Miniputt run logs from Claude"
category: RVV
---

Inspect RVV Miniputt logs.

Use:

```bash
scripts/rvv-miniputt logs <user-args>
```

Fallback if needed:

```bash
python3 -m tournament_scheduler.cli.rvv_cli logs <user-args>
```

Never run `/rvv-miniputt logs` in the shell. Summarize the output and highlight actionable failures.

Examples:
- `/rvv-miniputt:logs`
- `/rvv-miniputt:logs show latest`
- `/rvv-miniputt:logs stats`
