# Plan

**Feature:** Remove "Min ærlige dom" judgment section and consolidate into hero: both sections answer the same question ("is the plan good?") with different scoring systems that can contradict. Fix: (1) delete `render_opinionated_judgment_html` and its call site in html_exporter.py; (2) drive the hero's `overall_status` from the judgment tone (`rough→fail`, `mixed→warn`, `strong→pass`) instead of `fairness_gate.status`; (3) move the 4 detail cards (Matchup, Belastning, Hjemmeturneringer, Reise) from the judgment section into the hero as supporting detail. One evaluation, one section, no contradiction.
**Goal:** Remove "Min ærlige dom" judgment section and consolidate into hero: both sections answer the same question ("is the plan good?") with different scoring systems that can contradict. Fix: (1) delete `render_opinionated_judgment_html` and its call site in html_exporter.py; (2) drive the hero's `overall_status` from the judgment tone (`rough→fail`, `mixed→warn`, `strong→pass`) instead of `fairness_gate.status`; (3) move the 4 detail cards (Matchup, Belastning, Hjemmeturneringer, Reise) from the judgment section into the hero as supporting detail. One evaluation, one section, no contradiction.
**Backlog-ref:** 180
**Constraints:** none
**Date:** 2026-06-21
**Intent:** Eliminate the duplicate "is the plan good?" evaluation that creates contradictory pass/fail signals by consolidating the judgment tone and its 4 supporting cards into the existing hero section as the single source of truth.

## Tasks

- [x] Removed render_opinionated_judgment_html from judgment.py, its import and call site in html_exporter.py, and $ from the replacements dict and template. analyze_opinionated_judgment is preserved for reuse in subsequent tasks. — 2026-06-21
  - Files: `tournament_scheduler/html/renderers/judgment.py`, `tournament_scheduler/html/html_exporter.py`
  - Approach: Remove the `render_opinionated_judgment_html` function body from `judgment.py` and remove the corresponding import on line 52 of `html_exporter.py` along with the call around line 200 and the `$REPORT_JUDGMENT$` assignment around line 598. Keep `analyze_opinionated_judgment` intact as it will be reused.

- [ ] Switch `overall_status` derivation from `fairness_gate.status` to judgment tone in html_exporter.py
  - Files: `tournament_scheduler/html/html_exporter.py`
  - Approach: Replace the `status_rank` logic around lines 396-403 that reads `plan.fairness_gate.get("status")` with a direct mapping from the `tone` key of the `analyze_opinionated_judgment` result (`rough→fail`, `mixed→warn`, `strong→pass`), keeping the `blocked`/`cancelled` override to `warn` if needed.

- [ ] Add a `$REPORT_JUDGMENT_CARDS$` placeholder to the hero in `report_overview.html` and remove `$REPORT_JUDGMENT$`
  - Files: `tournament_scheduler/html/templates/report_overview.html`
  - Approach: Remove the `$REPORT_JUDGMENT$` line that appears after the hero div; add a `$REPORT_JUDGMENT_CARDS$` placeholder inside the hero div (below `$REPORT_NOTE$`) where the 4 detail cards will be injected.

- [ ] Render the 4 judgment cards (Matchup, Belastning, Hjemmeturneringer, Reise) as HTML and inject them into the hero via the new placeholder
  - Files: `tournament_scheduler/html/html_exporter.py`, `tournament_scheduler/html/renderers/judgment.py`
  - Approach: Add a new helper `render_judgment_cards_html(cards)` in `judgment.py` that produces a card-grid `<div>` from the 4-tuple list; call it in `html_exporter.py` after `analyze_opinionated_judgment` and assign the result to `$REPORT_JUDGMENT_CARDS$` in the replacements dict.

- [ ] Update hero status label and answer text to use judgment tone label and verdict instead of fairness-gate labels
  - Files: `tournament_scheduler/html/html_exporter.py`
  - Approach: In the section that sets `$REPORT_ANSWER$` and `$REPORT_NOTE$`, source the text from the `verdict` and `action_text` fields of the `analyze_opinionated_judgment` result instead of from the fairness gate, so the hero's prose and its status class both come from the same evaluation.

- [ ] Write or update tests to assert that the judgment section is absent and the hero status reflects judgment tone
  - Files: `tests/test_stage4_export.py`, `tests/test_html_exporter.py` (create if absent)
  - Approach: Add a test that generates a report HTML string from a minimal plan fixture and asserts: (1) the string does not contain `render_opinionated_judgment_html` references or the old section heading; (2) the hero div class matches the expected tone-derived status; (3) the 4 card labels appear inside the hero section.

## Log

- 2026-06-21 Plan created

## Acceptance Criteria

When the feature is done, the html_exporter.py file no longer calls or imports `render_opinionated_judgment_html` and the `$REPORT_JUDGMENT$` placeholder is no longer populated in the report template.
The overall_status in the hero section is derived from judgment tone (rough→fail, mixed→warn, strong→pass) rather than fairness_gate.status, so the hero class and judgment evaluation are always consistent.
The 4 detail cards (Matchup, Belastning, Hjemmeturneringer, Reise) are rendered within the hero section of the generated HTML, not in a separate judgment section after it.
The report_overview.html template no longer contains the `$REPORT_JUDGMENT$` placeholder and instead has the judgment cards injected inside the hero div.
Running `pytest` passes with tests confirming that `render_opinionated_judgment_html` is not called and the judgment tone drives hero status.

### 2026-06-21 — Removed render_opinionated_judgment_html from judgment.py, its import and call site in html_exporter.py, and $ from the replacements dict and template. analyze_opinionated_judgment is preserved for reuse in subsequent tasks.
**Rationale:** Straightforward deletion; judgment variable from analyze_opinionated_judgment is kept since later tasks will use it to drive overall_status.
**Findings:** Function deleted from judgment.py, import updated to only pull analyze_opinionated_judgment, judgment_html call and parameter removed from html_exporter.py, $ removed from template and replacements dict; all 672 tests pass.
LESSONS: none
**Files:** judgment.py (-42), html_exporter.py (-10/+1), report_overview.html (-2)
**Commit:** [pending — fill after commit]
