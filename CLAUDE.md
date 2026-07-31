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

## RVV Miniputt skill
When working with scraping, calendar generation, season planning, or pipeline debugging, use the RVV skill in `.agents/skills/rvv/SKILL.md`.

## RVV Miniputt commands in Claude
Claude does not load Pi extensions directly. In this repo, use the Claude project commands under `.claude/commands/rvv-miniputt/`:

- `/rvv-miniputt:run`
- `/rvv-miniputt:publish` — run the full pipeline and publish to GitHub Pages in one step, auto-confirmed (no approval pause)
- `/rvv-miniputt:status`
- `/rvv-miniputt:logs`
- `/rvv-miniputt:calendars`
- `/rvv-miniputt:guide`

These commands should execute the repo-local launcher, not the Pi slash command. Never run `/rvv-miniputt ...` via shell (`/rvv-miniputt run` will fail with `command not found`). The harness-neutral entrypoints are `scripts/rvv-miniputt ...` and `python3 -m tournament_scheduler.cli.rvv_cli ...`, as documented in `.agents/skills/rvv/SKILL.md`.

When planning or changing scheduling logic, always review whether the rules report and related docs need to be updated to match the new behavior.
