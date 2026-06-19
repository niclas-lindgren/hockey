# Plan: Dynamic report conclusion
**Goal:** Make the report's subjective conclusion dynamic: _report_overview_html currently has three static hardcoded string branches with no per-run data. Inject: tournament count + month span, the weakest named score metric + its value, most-travelling team and distance, number of blocked sources, and the specific fairness gate sub-metric that triggered warn/fail.
**Created:** 2026-06-19
**Intent:** Replace the three static Norwegian conclusion strings with per-run data so reviewers see concrete plan facts directly in the hero summary instead of generic boilerplate.
**Backlog-ref:** 136

## Tasks
- [x] Added most_travel_team: str and most_travel_km: str keyword parameters to _report_overview_html and updated the call site in export() to pass them from the already-computed tuple. — 2026-06-19
  - Files: /Users/niclasl/src/hockey/tournament_scheduler/html/html_exporter.py
  - Approach: Add `most_travel_team: str` and `most_travel_km: str` keyword parameters to `_report_overview_html`'s signature, and update the call site in `export()` at line 203 to pass them from the already-computed tuple at line 125.

- [x] Inside _report_overview_html, derive Norwegian month-span (e.g. 'september–desember') from plan.start_date and plan.end_date, falling back to date_range if either is None. — 2026-06-19
  - Files: /Users/niclasl/src/hockey/tournament_scheduler/html/html_exporter.py
  - Approach: Inside `_report_overview_html`, derive a Norwegian month-span string (e.g. "oktober–mars") from `plan.start_date` and `plan.end_date` (both `Optional[date]`); fall back to `date_range` if either is None.

- [x] Replaced static answer_by_status strings with format templates embedding {tournament_count} and {month_span}; applied .format() at the _answer_base assignment where active_tournaments is in scope. — 2026-06-19
  - Files: /Users/niclasl/src/hockey/tournament_scheduler/html/html_exporter.py
  - Approach: Replace the static `answer_by_status` strings (lines 387–391) and `note_by_status` strings (lines 392–396) with f-string or `.format()` templates that embed `len(active_tournaments)` and the month-span string, so every status branch surfaces the tournament count.

- [x] Extended the _detail_parts block to append the numeric score: 'Svakeste metrikk: {label} ({score}%).' using weakest_metric['score']. — 2026-06-19
  - Files: /Users/niclasl/src/hockey/tournament_scheduler/html/html_exporter.py
  - Approach: The `weakest_metric` dict (line 420) already provides `label` (used) and `score` (int, 0–100); extend the `_detail_parts` block (lines 441–448) to append `f"Svakeste metrikk: {weakest_metric_name} ({weakest_metric['score']}%)."` instead of the label-only string.

- [x] In _detail_parts, appended 'Mest reisende lag: {most_travel_team} (~{most_travel_km} km).' when most_travel_team is non-empty and most_travel_km ! '0'. — 2026-06-19
  - Files: /Users/niclasl/src/hockey/tournament_scheduler/html/html_exporter.py
  - Approach: In `_detail_parts`, append `f"Mest reisende lag: {most_travel_team} (~{most_travel_km} km)."` when `most_travel_team` is non-empty and `most_travel_km != "0"`, using the newly-added parameters from task 1.

- [x] For warn/fail overall_status, append 'Fairness-avvik: {label} – {detail}' to _detail_parts when a weakest_metric with non-empty detail exists. — 2026-06-19
  - Files: /Users/niclasl/src/hockey/tournament_scheduler/html/html_exporter.py
  - Approach: `weakest_metric` (line 420) already identifies the worst gate sub-metric; append its `detail` string or `f"Fairness-avvik: {weakest_metric['label']} – {weakest_metric['detail']}"` to `_detail_parts` for warn/fail status, distinct from the earlier metric-name-only append.

- [x] Added 5 new test functions to TestRunStage4: test_conclusion_injects_tournament_count, test_conclusion_injects_month_span, test_conclusion_injects_most_travel_team, test_conclusion_injects_weakest_metric_score, test_conclusion_injects_fairness_submetric_detail. All 27 tests pass. — 2026-06-19
  - Files: /Users/niclasl/src/hockey/tests/test_stage4_export.py
  - Approach: Extend the existing test class with new test functions that assert tournament count string, month-span string, most-travel team name, weakest metric score value, and fairness sub-metric detail appear in `report_html`; follow the pattern of `test_conclusion_injects_weakest_metric_name` at line 573.

## Notes
- `most_travel_team` and `most_travel_km` are already computed in `export()` at line 125 but are NOT currently passed to `_report_overview_html` — they must be wired through.
- `plan.start_date` and `plan.end_date` are `Optional[date]`; month name extraction should use `.strftime("%B")` or a Norwegian month lookup.
- `weakest_metric` dict has keys: `label`, `score`, `status`, `detail`.
- Existing tests `test_conclusion_injects_weakest_metric_name` and `test_conclusion_injects_blocked_count` in tests/test_stage4_export.py must continue to pass.
- The `_detail_parts` list is joined with spaces and appended to `_answer_base` (line 448); keep same mechanism.

## Acceptance Criteria
- [ ] The report HTML output contains the active tournament count and a month-span string in the REPORT_ANSWER section.
- [ ] The report HTML output contains the weakest fairness metric label and its numeric score value (e.g. "60%") in the conclusion.
- [ ] The report HTML output contains the most-travelling team name and its distance in km when travel data is present.
- [ ] The report HTML output contains the specific fairness gate sub-metric detail for any plan whose gate status is warn or fail.
- [ ] All existing tests in tests/test_stage4_export.py pass after the changes.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-19 — Added most_travel_team: str and most_travel_km: str keyword parameters to _report_overview_html and updated the call site in export() to pass them from the already-computed tuple.
**Rationale:** Straightforward parameter passthrough — values already computed at line 125.
**Findings:** Call site now passes most_travel_team and most_travel_km to _report_overview_html.
LESSONS: none
**Files:** html_exporter.py (+10/-1)
**Commit:** [pending — fill after commit]

### 2026-06-19 — Inside _report_overview_html, derive Norwegian month-span (e.g. 'september–desember') from plan.start_date and plan.end_date, falling back to date_range if either is None.
**Rationale:** Used a simple _NO_MONTHS list indexed by month number; fallback to date_range for robustness.
**Findings:** month_span now available as a local variable in _report_overview_html.
LESSONS: none
**Files:** html_exporter.py (+11/-0)
**Commit:** [pending — fill after commit]

### 2026-06-19 — Replaced static answer_by_status strings with format templates embedding {tournament_count} and {month_span}; applied .format() at the _answer_base assignment where active_tournaments is in scope.
**Rationale:** Templates use .format() to keep dict keys readable and avoid f-string complexity at definition time.
**Findings:** Conclusion now reads e.g. 'Ja, planen (2 turneringer, september–desember) ser brukbar ut...'.
LESSONS: The existing test that checked for the old exact static string needed updating — the phrase 'planen ser brukbar' is no longer adjacent because the count/month are injected between 'planen' and 'ser brukbar'.
**Files:** html_exporter.py (+8/-4)
**Commit:** [pending — fill after commit]

### 2026-06-19 — Extended the _detail_parts block to append the numeric score: 'Svakeste metrikk: {label} ({score}%).' using weakest_metric['score'].
**Rationale:** Appended score in parentheses after the label — concise and consistent with dashboard display.
**Findings:** Conclusion now shows both label and score for the weakest fairness metric.
LESSONS: none
**Files:** html_exporter.py (+1/-1)
**Commit:** [pending — fill after commit]

### 2026-06-19 — In _detail_parts, appended 'Mest reisende lag: {most_travel_team} (~{most_travel_km} km).' when most_travel_team is non-empty and most_travel_km ! '0'.
**Rationale:** Guard conditions prevent empty or zero-km entries from polluting the conclusion.
**Findings:** Conclusion now surfaces the most-travelling team when travel data is available.
LESSONS: none
**Files:** html_exporter.py (+3/-0)
**Commit:** [pending — fill after commit]

### 2026-06-19 — For warn/fail overall_status, append 'Fairness-avvik: {label} – {detail}' to _detail_parts when a weakest_metric with non-empty detail exists.
**Rationale:** Distinct from the label-only metric line — shows the full actionable detail for organizers to act on.
**Findings:** Conclusion now shows both the metric score summary and the specific detail for warn/fail plans.
LESSONS: none
**Files:** html_exporter.py (+5/-0)
**Commit:** [pending — fill after commit]

### 2026-06-19 — Added 5 new test functions to TestRunStage4: test_conclusion_injects_tournament_count, test_conclusion_injects_month_span, test_conclusion_injects_most_travel_team, test_conclusion_injects_weakest_metric_score, test_conclusion_injects_fairness_submetric_detail. All 27 tests pass.
**Rationale:** Followed the pattern of test_conclusion_injects_weakest_metric_name — each test sets up a targeted plan dict and asserts the specific string appears in report_html.
**Findings:** 27 tests all pass; each new test isolates one injected data point.
LESSONS: none
**Files:** tests/test_stage4_export.py (+63/-1)
**Commit:** [pending — fill after commit]
