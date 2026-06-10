# Plan: Fix /rvv-miniputt literal-string references
**Goal:** All `/rvv-miniputt` references in code and HTML are either removed (where they can't execute) or corrected to the proper CLI invocation.
**Created:** 2026-06-10
**Intent:** Several places reference `/rvv-miniputt` with a leading slash, which makes it look like a path or literal string instead of a CLI command. The HTML report has a clickable link that can never execute the CLI. Fix all references.
**Backlog-ref:** 37

## Tasks
- [x] Fix `calendars.html` "Tving re-skraping" link — replace with help text instead of broken href
  - Files: tournament_scheduler/pipeline/calendar_viewer.py
  - Approach: Replace `<a class="refresh-btn green" href="/rvv-miniputt calendars --refresh">` with a styled `<span>` or `<code>` showing the command text. The HTML is static and can't execute CLI commands.
- [x] Fix remaining `/rvv-miniputt` references — strip leading slash or convert to proper formatting
  - Files: tournament_scheduler/pipeline/calendar_viewer.py, tournament_scheduler/tools/calendar_compare.py
  - Approach: Replace `/rvv-miniputt` with `rvv-miniputt` in Norwegian messages (the leading slash is wrong for CLI commands). Keep docstring references as-is since they're code documentation.

## Notes
- The main issue is the HTML link: `<a href="/rvv-miniputt calendars --refresh">` navigates to a path that doesn't exist. Browser can't run CLI tools.
- The `calendar_compare.py` message: `"kjør /rvv-miniputt run"` — the slash is incorrect Norwegian CLI convention.
- The pipeline runs fine — the "literal string" issue was user confusion from the HTML link and message formatting.

## Acceptance Criteria
- [x] `calendars.html` no longer contains an `href="/rvv-miniputt"` link — replaced with instructional text
- [x] No user-facing Norwegian messages contain `/rvv-miniputt` (should be just `rvv-miniputt`)
- [x] grep: no occurrence of `/rvv-miniputt` in HTML template output or Norwegian-language CLI messages

## Log


### 2026-06-10 — Fix remaining `/rvv-miniputt` references — strip leading slash or convert to proper formatting
**Done:** Fixed all 3 remaining /rvv-miniputt references: calendar_viewer.py CLI message, calendar_compare.py warning message, tournament_updater.py docstring. All now use rvv-miniputt without leading slash.
**Rationale:** The leading slash is wrong for CLI commands and looks like a path. Fixed all user-facing messages and docstrings.
**Findings:** Zero occurrences of /rvv-miniputt remain in the codebase.
**Files:** tournament_scheduler/pipeline/calendar_viewer.py (+1/-1), tournament_scheduler/tools/calendar_compare.py (+1/-1), tournament_scheduler/pipeline/tournament_updater.py (+1/-1)
**Commit:** not committed
### 2026-06-10 — Fix `calendars.html` "Tving re-skraping" link — replace with help text instead of broken href
**Done:** Replaced broken href= /rvv-miniputt link with styled span showing CLI command as code text. HTML reports can't execute CLI tools.
**Rationale:** Browser links can't execute CLI commands. Replaced with instructional code text.
**Findings:** Also added CLI hint CSS. The link was the main source of literal-string confusion.
**Files:** tournament_scheduler/pipeline/calendar_viewer.py (+5/-2)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
