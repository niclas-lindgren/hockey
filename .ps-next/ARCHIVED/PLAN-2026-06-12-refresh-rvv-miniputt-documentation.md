# Plan: Refresh RVV Miniputt documentation
**Goal:** Update the project docs so they accurately describe the current four-stage RVV Miniputt pipeline, its commands, inputs, and outputs.
**Created:** 2026-06-12
**Intent:** Replace the outdated single-tournament scheduler wording with documentation that matches the current pipeline and operator workflows.
**Backlog-ref:** 64

## Tasks
- [x] Rewrite the top-level README for the current RVV Miniputt workflow
  - Files: README.md
  - Approach: Replace the legacy conflict-scheduler-centric overview with a concise project summary, current `rvv-miniputt` command list, pipeline stages, and the key operator flows (run, calendars, scrape, scrape-llm, logs, cancel/replan).
- [x] Add a dedicated pipeline guide with config, credentials, and export details
  - Files: docs/rvv-miniputt-pipeline.md
  - Approach: Document `input.json` and roster formats, BookUp credential handling, timestamped export directories, HTML/Excel/CSV/iCal/Spond outputs, and the resume/status/log handoff expectations used by operators.

## Notes
- The current README still describes the older tournament-scheduling app, so it should be rewritten rather than patched piecemeal.
- CLI behavior should be documented from the current `tournament_scheduler/cli/rvv_cli.py` implementation.
- Keep the docs aligned with the four pipeline stages and current output formats; avoid claiming unsupported commands or legacy workflows.

## Acceptance Criteria
- [ ] `README.md` mentions the current `rvv-miniputt` pipeline commands and no longer centers the old single-tournament conflict-checker flow.
- [ ] `docs/rvv-miniputt-pipeline.md` contains sections for `input.json`, `sources`, BookUp credentials, timestamped exports, and the available export formats.
- [ ] The docs describe how operators resume, inspect status/logs, or recover from partial runs without referencing deprecated behavior.

## Log


### 2026-06-12 — Add a dedicated pipeline guide with config, credentials, and export details
**Done:** Added `docs/rvv-miniputt-pipeline.md` with pipeline stages, `input.json` schema, source handling, BookUp credentials, export formats, and recovery flows.
**Rationale:** A dedicated guide keeps the README concise while providing the deeper operational reference requested by the backlog item.
**Findings:** The new guide documents the checkpointed `.pipeline/` workflow and the standard recovery loop for blocked sources and partial runs.
**Files:** docs/rvv-miniputt-pipeline.md
**Commit:** not committed
### 2026-06-12 — Rewrite the top-level README for the current RVV Miniputt workflow
**Done:** Rewrote `README.md` around the current four-stage RVV Miniputt pipeline, current commands, inputs, and outputs.
**Rationale:** The root README needed to stop reading like the legacy single-tournament scheduler docs and instead reflect the operator-facing pipeline.
**Findings:** The README now points readers to the dedicated pipeline guide and lists the active `rvv-miniputt` workflows, including the Pi slash-command equivalents.
**Files:** README.md
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
