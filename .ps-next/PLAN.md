# Plan: Fix season_plan.html age-group filter dropdown
**Goal:** The age-group filter dropdown is driven entirely by the configured `age_groups` from the season plan data — no hardcoded options.
**Created:** 2026-06-11
**Intent:** Currently `filters.html` hardcodes `<option>` for U10 and U11, and the Python code only fills `$EXTRA_AGE_OPTIONS$` for groups other than those two. When a season plan includes U8/U9/U12 etc. but NOT U10/U11, the dropdown shows irrelevant dead options. The dropdown must reflect the actual age groups present in the plan.
**Backlog-ref:** 44

## Tasks
- [x] Replace hardcoded U10/U11 filter options with dynamic generation
  - Files: tournament_scheduler/html/templates/filters.html, tournament_scheduler/html/html_exporter.py
  - Approach: In `filters.html`, replace the two hardcoded `<option value="U10">U10</option>` / `<option value="U11">U11</option>` lines plus `$EXTRA_AGE_OPTIONS$` with a single `$AGE_GROUP_OPTIONS$` placeholder. In `html_exporter.py`, rename the variable `extra_age_options` → `age_group_options`, remove the `if ag not in ("U10", "U11")` filter so ALL age groups from the plan are emitted, and update the `$EXTRA_AGE_OPTIONS$` → `$AGE_GROUP_OPTIONS$` replacement key.

## Notes
- The `$AGE_GROUPS$` placeholder (header subtitle and "Alle (...)" label) is already dynamic — driven by `" + ".join(age_groups)` in `html_exporter.py`. No changes needed there.
- The JavaScript `render()` function already filters correctly by `t.g` — no JS changes needed.

## Acceptance Criteria
- [ ] `filters.html` contains no hardcoded age-group `<option>` elements
- [ ] `html_exporter.py` creates option tags for every age group in the plan, without filtering out U10/U11
- [ ] The generated HTML dropdown contains exactly the age groups present in the season plan data

## Log

### 2026-06-11 — Replace hardcoded U10/U11 filter options with dynamic generation
**Done:** Removed hardcoded U10/U11 option elements from filters.html template, replaced with $AGE_GROUP_OPTIONS$ placeholder. In html_exporter.py, renamed extra_age_options to age_group_options and removed the if ag not in (U10, U11) filter so all age groups from the season plan are emitted as options.
**Rationale:** The filter dropdown must reflect the actual age groups in the season plan, not assume U10/U11 are always present. The template variable and Python logic now emit one option per configured age group.
**Findings:** filters.html is not git-tracked (template file). The $AGE_GROUPS$ header variable was already dynamic. The JavaScript filtering logic was already correct based on t.g comparison.
**Files:** tournament_scheduler/html/templates/filters.html (-2 hardcoded options + placeholder), tournament_scheduler/html/html_exporter.py (variable rename, removed filter condition, placeholder rename)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
