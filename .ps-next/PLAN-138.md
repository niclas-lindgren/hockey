# Plan: Add issue count to the hero verdict pill in the report

**Feature:** Add issue count to the hero verdict pill in the report: the action list exists but its count is not summarised in the verdict block, forcing the reader to scroll to discover whether anything needs fixing.
**Goal:** The hero verdict pill shows the issue count so the reader immediately sees whether anything needs fixing without scrolling.
**Backlog-ref:** 138
**Constraints:** none
**Date:** 2026-06-19
**Intent:** Surface the action item count directly in the hero verdict pill so organizers can see at a glance whether the plan has issues without scrolling to the action list.

---

## Tasks

- [x] Added REPORT_ACTION_COUNT placeholder to the hero verdict pill in report_overview.html and wired it to issue_count in html_exporter.py. — 2026-06-19
  - Files: `tournament_scheduler/html/templates/report_overview.html`
  - Approach: Modify line 10 of report_overview.html to embed `$REPORT_ACTION_COUNT$` inside the status pill span alongside `$REPORT_STATUS_LABEL$`, for example `$REPORT_STATUS_LABEL$ · $REPORT_ACTION_COUNT$ punkt(er)` so the count appears inline in the pill.

- [x] Computed issue_count  len(actions) before the default pass placeholder is appended; already implemented in the previous commit. — 2026-06-19
  - Files: `tournament_scheduler/html/html_exporter.py`
  - Approach: After the `actions` list is finalised (line 421), compute `real_action_count = 0 if (len(actions) == 1 and actions[0][0] == "pass") else len(actions)` and store it; this avoids re-scanning the list when building the replacements dict.

- [x] Injected REPORT_ACTION_COUNT into the replacements dict as str(issue_count); already implemented in the prior commit. — 2026-06-19
  - Files: `tournament_scheduler/html/html_exporter.py`
  - Approach: Add `"$REPORT_ACTION_COUNT$": str(real_action_count)` to the replacements dict at lines 538-552 so the placeholder is substituted alongside the existing status label and answer text.

- [x] Added assertions in test_generates_html_with_configured_age_group_filters (1 punkt(er)) and test_conclusion_injects_weakest_metric_name (4 punkt(er)) to verify action count appears in the hero verdict pill. — 2026-06-19
  - Files: `tests/test_stage4_export.py`
  - Approach: Add an assertion in the existing report-HTML regression test that the rendered output contains the action count string (e.g. `"0 punkt(er)"` for a clean plan, or a non-zero count for a plan with metric warnings), following the pattern already used for other pill/status assertions.

---

## Log

- 2026-06-19 Plan created for backlog item 138

---

## Acceptance Criteria

The hero verdict pill in the generated report HTML contains the total issue count when there are actionable items present.
The report generation process produces a hero verdict pill that shows "0" (or equivalent label) when no critical actions exist — i.e. the actions list contains only the "pass" entry.
The CLI export command outputs a report where the hero verdict pill shows the correct issue count matching the number of non-pass actions.
The exported `season_plan_report.html` contains the action count inline in the pill element, verifiable by searching for the placeholder substitution result.
The test suite passes after adding the count assertion without modifying existing test expectations.

### 2026-06-19 — Added REPORT_ACTION_COUNT placeholder to the hero verdict pill in report_overview.html and wired it to issue_count in html_exporter.py.
**Rationale:** none
**Findings:** issue_count is computed before the default pass action is appended so it reflects real issues only (0 when status is pass).
LESSONS: none
**Files:** html_exporter.py (+2/-0), report_overview.html (+1/-1)
**Commit:** 73292e6 (hockey)

### 2026-06-19 — Computed issue_count  len(actions) before the default pass placeholder is appended; already implemented in the previous commit.
**Rationale:** none
**Findings:** Already done in prior commit alongside the template change.
LESSONS: none
**Files:** html_exporter.py (+1/-0)
**Commit:** 73292e6

### 2026-06-19 — Injected REPORT_ACTION_COUNT into the replacements dict as str(issue_count); already implemented in the prior commit.
**Rationale:** none
**Findings:** Already done in prior commit alongside template and issue_count changes.
LESSONS: none
**Files:** html_exporter.py (+1/-0)
**Commit:** 73292e6

### 2026-06-19 — Added assertions in test_generates_html_with_configured_age_group_filters (1 punkt(er)) and test_conclusion_injects_weakest_metric_name (4 punkt(er)) to verify action count appears in the hero verdict pill.
**Rationale:** none
**Findings:** Actual counts differ from naive estimates: the clean plan produces 1 (not 0) because missing_hosts fires for clubs with no home tournament; the warn plan produces 4 (gate + 2 metrics + missing_hosts).
LESSONS: Always verify action count by running the plan before asserting a number — missing_hosts adds 1 action for any plan that does not host all 9 RVV clubs.
**Files:** test_stage4_export.py (+4/-0)
**Commit:** [pending — fill after commit]
