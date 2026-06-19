# Plan: Restructure report layout

**Feature:** Restructure report layout: (1) move the judgment block ($JUDGMENT$) up to immediately follow the hero verdict instead of appearing after 8 data sections; (2) collapse the advisory review section (review.py) behind a <details> toggle by default — it duplicates content already shown as action items; (3) group numeric detail sections (scores, metrics, fairness adjustments, club dashboard, team stats, travel stats) under a single collapsible Detaljer accordion.
**Goal:** Restructure report layout: (1) move the judgment block ($JUDGMENT$) up to immediately follow the hero verdict instead of appearing after 8 data sections; (2) collapse the advisory review section (review.py) behind a <details> toggle by default — it duplicates content already shown as action items; (3) group numeric detail sections (scores, metrics, fairness adjustments, club dashboard, team stats, travel stats) under a single collapsible Detaljer accordion.
**Backlog-ref:** 137
**Constraints:** none
**Date:** 2026-06-19
**Intent:** Improve report readability by surfacing the most actionable content (judgment verdict) immediately after the hero, hiding redundant advisory review detail behind a toggle, and collapsing raw numeric diagnostics so they don't dominate the page.

## Tasks

- [x] Added $REPORT_JUDGMENT$ placeholder after hero div in report_overview.html and wired judgment_html into it in _report_overview_html; removed judgment_html from advisory_html. — 2026-06-19
  - Files: `tournament_scheduler/html/templates/report_overview.html`, `tournament_scheduler/html/html_exporter.py`
  - Approach: Insert `$REPORT_JUDGMENT$` directly after the closing `</div>` of the `report-hero` div in report_overview.html. In `_report_overview_html`, add `"$REPORT_JUDGMENT$": judgment_html` to the replacements dict. Remove `judgment_html` from `advisory_html` so it no longer appears in the advisory section.

- [x] Converted #advisoryChecks section from open <section> to a <details class'report-section report-section--collapsible'> with <summary class'section-head'>, matching the #ruleTransparency pattern. Defaults closed. — 2026-06-19
  - Files: `tournament_scheduler/html/templates/report_overview.html`
  - Approach: Change the `#advisoryChecks` section from an open `<section>` to a `<details class="report-section report-section--collapsible">` element (without the `open` attribute so it defaults to closed), with `<summary class="section-head">` wrapping the heading, matching the existing pattern used for `#ruleTransparency`.

- [ ] Group the existing diagnostics and rule transparency sections into a single collapsible Detaljer accordion in report_overview.html
  - Files: `tournament_scheduler/html/templates/report_overview.html`
  - Approach: Wrap the `#ruleTransparency` details block, `#advisoryChecks` (now also a details), and `#detailedDiagnosticsIntro` inside a new outer `<details class="report-section report-section--collapsible" id="detaljerAccordion">` with a `<summary>` labelled "Detaljer". This accordion is closed by default and contains all numeric detail sections.

- [ ] Inject scores, metrics, and club dashboard content into the Detaljer accordion in report_overview.html and html_exporter.py
  - Files: `tournament_scheduler/html/templates/report_overview.html`, `tournament_scheduler/html/html_exporter.py`
  - Approach: Add `$REPORT_SCORES$`, `$REPORT_METRICS$`, and `$REPORT_CLUB_DASHBOARD$` placeholders inside the new Detaljer accordion in report_overview.html. In `_report_overview_html`, populate them using the existing SCORES, METRICS, and CLUB_DASHBOARD template constants (import them from `templates` and add substitution entries in the replacements dict).

- [ ] Update tests to reflect new report layout structure
  - Files: `tests/` (any test that checks report HTML structure or section ordering)
  - Approach: Search for tests asserting report section order, the advisory section, or the diagnostics section; update expected HTML patterns to match the new judgment position, collapsed advisory toggle, and Detaljer accordion structure.

## Acceptance Criteria

When the report layout is restructured, the judgment block should immediately follow the hero verdict in the output HTML.
When the report layout is restructured, the advisory review section should be collapsed by default and contain a <details> toggle element.
When the report layout is restructured, the numeric detail sections should be grouped under a single collapsible Detaljer accordion that contains scores, metrics, fairness adjustments, club dashboard, team stats, and travel stats.
When the report layout is restructured, the diagnostics section should no longer be visible by default and should instead be contained within the new Detaljer accordion.
When the report layout is restructured, the rule transparency section should continue to use the <details> pattern and remain functional as a collapsible section.

## Log
- 2026-06-19 Plan created

### 2026-06-19 — Added $REPORT_JUDGMENT$ placeholder after hero div in report_overview.html and wired judgment_html into it in _report_overview_html; removed judgment_html from advisory_html.
**Rationale:** Straightforward template change — no alternatives considered.
**Findings:** judgment_html now renders immediately after the hero verdict; advisory section shows only review_summary_html.
LESSONS: none
**Files:** html_exporter.py (+3/-1), report_overview.html (+2/-0)
**Commit:** 59b3b34 (hockey)

### 2026-06-19 — Converted #advisoryChecks section from open <section> to a <details class'report-section report-section--collapsible'> with <summary class'section-head'>, matching the #ruleTransparency pattern. Defaults closed.
**Rationale:** Straightforward pattern match to existing ruleTransparency collapsible — no alternatives considered.
**Findings:** Advisory section now collapses by default using same details/summary pattern as ruleTransparency.
LESSONS: none
**Files:** report_overview.html (+4/-4)
**Commit:** [pending — fill after commit]
