---
name: "RVV Miniputt: Calendars"
description: "Generate RVV Miniputt calendar reports from Claude"
category: RVV
---

Generate RVV Miniputt calendar reports.

Use:

```bash
scripts/rvv-miniputt calendars <user-args>
```

Fallback if needed:

```bash
python3 -m tournament_scheduler.cli.rvv_cli calendars <user-args>
```

Never run `/rvv-miniputt calendars` in the shell. Report where the calendar output was written if the command succeeds.
