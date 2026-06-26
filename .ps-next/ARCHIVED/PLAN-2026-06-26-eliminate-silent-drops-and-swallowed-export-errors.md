# Plan: Eliminate silent drops and swallowed export errors
**Goal:** Log a warning whenever pipeline input, plan data, or export metadata is discarded instead of failing silently.
**Created:** 2026-06-25
**Intent:** Prevent hidden data loss so workbook typos, bad checkpoint rows, and export fallback failures are visible during normal runs.
**Backlog-ref:** 2

## Tasks
- [x] Warn when Stage 1 discards unhandled config keys
  - Files: tournament_scheduler/pipeline/stage1_helpers.py, tests/test_stage1_config.py
  - Approach: detect raw workbook keys that are not preserved by `_parse_config`, emit a single `logger.warning(...)` before dropping them, and add a regression test that feeds a custom workbook key and asserts the warning is logged.

- [x] Log Stage 4 game drops caused by missing team labels
  - Files: tournament_scheduler/pipeline/stage4_helpers.py, tests/test_stage4_export.py
  - Approach: when `_dict_to_plan` cannot resolve a game's home/away label, keep skipping the bad game but emit a warning with the tournament/date/team labels; add a test that verifies valid games still load and the warning appears for the bad row.

- [x] Replace silent Stage 4 export fallbacks with contextual warnings
  - Files: tournament_scheduler/pipeline/stage4_export.py, tests/test_stage4_export.py
  - Approach: add logging around the envelope/cache/scrape-age fallback blocks so exceptions are reported instead of swallowed, while preserving best-effort export output; add a targeted regression test for one fallback path.

## Notes
- Stage 3 event parsing already logs malformed-event warnings and is covered by existing tests; no code change is expected there.
- Keep the warnings concise and Norwegian-friendly where the surrounding code already emits user-facing text.
- Do not change the underlying skip/continue behavior for this backlog item; only make the loss visible.

## Acceptance Criteria
- [ ] Unit tests pass while logging warnings for ignored Stage 1 config keys, dropped Stage 4 games, and Stage 4 export fallback failures.
- [ ] Running the relevant unit tests shows warnings for ignored Stage 1 config keys, dropped Stage 4 games, and Stage 4 export fallback failures.

## Log



### 2026-06-25 — Replace silent Stage 4 export fallbacks with contextual warnings
**Done:** Logged warnings for Stage 4 fallback failures when reading the scraping envelope and scrape cache, and for unreadable updated_at timestamps.
**Rationale:** Best-effort export should remain best-effort, but the swallowed exceptions now leave an audit trail.
**Findings:** The nested `try/except` blocks in the HTML export path were the main silent failure points; they now emit warnings instead of disappearing.
**Files:** tournament_scheduler/pipeline/stage4_export.py, tournament_scheduler/html/templates/report_overview.html, tests/test_stage4_export.py, .ps-next/PLAN.md
**Commit:** not committed
### 2026-06-25 — Log Stage 4 game drops caused by missing team labels
**Done:** Added warnings when `_dict_to_plan` skips games whose team labels cannot be resolved.
**Rationale:** Corrupted checkpoint rows should not disappear silently, but valid games must still load.
**Findings:** Stage 4 can keep its permissive fallback while surfacing the tournament/date and missing labels in the warning text.
**Files:** tournament_scheduler/pipeline/stage4_helpers.py, tests/test_stage4_export.py, .ps-next/PLAN.md
**Commit:** not committed
### 2026-06-25 — Warn when Stage 1 discards unhandled config keys
**Done:** Added a warning for ignored workbook keys before `_parse_config` drops them.
**Rationale:** Silent config typos should be visible to operators without changing the successful parse path.
**Findings:** The workbook parser already normalizes the preserved keys; the new warning can safely report any extra keys that are not carried into the Stage 1 checkpoint.
**Files:** tournament_scheduler/pipeline/stage1_helpers.py, tests/test_stage1_config.py, .ps-next/PLAN.md
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
