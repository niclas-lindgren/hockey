# Plan: Data-driven report conclusion template
**Goal:** Replace the removed LLM narrative in the report conclusion with a static template that injects the weakest metric name, blocked source count, and cancellation count as concrete values from data already computed by `_report_overview_html`.
**Created:** 2026-06-18
**Intent:** Satisfy backlog item 136 by making the report conclusion informative with real per-run data — weakest metric, blocked sources, cancellations — without introducing any LLM dependency in the pipeline.
**Backlog-ref:** 154

## Tasks
- [x] Extract weakest metric name from metric_warnings sorted by status (fail first) then score ascending, stored as weakest_metric_name. — 2026-06-18
  - Files: tournament_scheduler/html/html_exporter.py
  - Approach: In `_report_overview_html`, after `metric_warnings` is built, derive `weakest_metric_name` as the `name` field of the first entry sorted by score ascending (or the entry with status `fail` first, then `warn`). If `metric_warnings` is empty, set it to `None`.

- [x] Build dynamic answer string with injected concrete values using f-string interpolation of weakest_metric_name, blocked count, and cancelled_count. — 2026-06-18
  - Files: tournament_scheduler/html/html_exporter.py
  - Approach: Replace the plain `answer_by_status` / `note_by_status` dict lookup with a function or inline block that formats Norwegian strings using `f-string` interpolation of `weakest_metric_name`, `len(blocked)`, and `cancelled_count` — e.g. "Svakeste metrikk: {weakest_metric_name}" appended to the base status string when the value is non-None/non-zero. Keep the three-branch pass/warn/fail structure.

- [x] The dynamically-built answer and note strings with injected values are correctly substituted into $ and $ template placeholders via existing replacements dict. — 2026-06-18
  - Files: tournament_scheduler/html/html_exporter.py
  - Approach: Ensure the dynamically-built `answer` and `note` strings (with injected values) are what gets substituted for `$REPORT_ANSWER$` and `$REPORT_NOTE$` in the template rendering call, replacing any leftover judgment_addendum that used fixed tone strings with no data.

- [x] Deleted judgment_addendum and judgment_note_addendum tone string dicts; removed judgment_tone extraction as it was only used for those dicts. — 2026-06-18
  - Files: tournament_scheduler/html/html_exporter.py
  - Approach: Delete or reduce the `judgment_addendum` / `judgment_note_addendum` dictionaries keyed on `judgment_tone` (currently "strong" / "mixed" / "rough") that append opaque fixed strings — these add no data. If judgment tone is still useful, integrate it as a brief qualifier rather than the only dynamic content.

- [x] Added 3 new test functions verifying weakest_metric_name, blocked count, and cancelled_count appear in rendered conclusion HTML; updated 2 existing assertions that checked old judgment_addendum text. — 2026-06-18
  - Files: tests/test_stage4_export.py
  - Approach: Add assertions to existing Stage 4 export tests (or a new test function) that render a sample plan with known `metric_warnings`, `blocked`, and `cancelled_count` values and assert the rendered HTML contains the expected weakest metric name string, blocked count, and cancellation count as substrings of the conclusion section.

## Notes
Constraints: none
`_report_overview_html` already has all required inputs: `blocked` (list), `cancelled_count` (int), `metric_warnings` (list of dicts with `name`/`status`/`score` keys), `gate_status` (str). No new computation is needed — only injection into the conclusion text. The existing `answer_by_status` / `note_by_status` dicts produce static Norwegian text; these should be extended with f-string interpolation, not replaced with a full template engine.

## Acceptance Criteria
- [ ] The report generation outputs conclusion HTML that contains the weakest metric name as a concrete string when metric_warnings is non-empty.
- [ ] The rendered $REPORT_ANSWER$ and $REPORT_NOTE$ sections contain the blocked source count and cancellation count as numeric values when those counts are non-zero.
- [ ] The pipeline produces the report conclusion without calling any LLM client — no call to generate_report_conclusion or any external model is present in the rendering path.
- [ ] All existing stage 4 export tests pass after the change.
- [ ] The updated html_exporter.py has no reference to judgment_addendum fixed tone strings that inject opaque text with no data values.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-18 — Extract weakest metric name from metric_warnings sorted by status (fail first) then score ascending, stored as weakest_metric_name.
**Rationale:** Straightforward sort on existing metric_warnings list.
**Findings:** weakest_metric_name is None when metric_warnings is empty.
LESSONS: none
**Files:** tournament_scheduler/html/html_exporter.py (+4/-0)
**Commit:** [pending — fill after commit]

### 2026-06-18 — Build dynamic answer string with injected concrete values using f-string interpolation of weakest_metric_name, blocked count, and cancelled_count.
**Rationale:** none
**Findings:** Answer string now appends specific data points when non-empty/non-zero.
LESSONS: none
**Files:** tournament_scheduler/html/html_exporter.py (+8/-2)
**Commit:** [pending — fill after commit]

### 2026-06-18 — The dynamically-built answer and note strings with injected values are correctly substituted into $ and $ template placeholders via existing replacements dict.
**Rationale:** No change needed to substitution logic — existing code already handles it.
**Findings:** Confirmed answer/note flow through replacements dict unchanged.
LESSONS: none
**Files:** tournament_scheduler/html/html_exporter.py (+0/-0)
**Commit:** [pending — fill after commit]

### 2026-06-18 — Deleted judgment_addendum and judgment_note_addendum tone string dicts; removed judgment_tone extraction as it was only used for those dicts.
**Rationale:** none
**Findings:** Removed 10 lines of opaque fixed-tone strings; answer now uses only data-driven content.
LESSONS: none
**Files:** tournament_scheduler/html/html_exporter.py (+0/-10)
**Commit:** [pending — fill after commit]

### 2026-06-18 — Added 3 new test functions verifying weakest_metric_name, blocked count, and cancelled_count appear in rendered conclusion HTML; updated 2 existing assertions that checked old judgment_addendum text.
**Rationale:** none
**Findings:** All 19 tests pass including the 3 new conclusion-injection tests.
LESSONS: none
**Files:** tests/test_stage4_export.py (+52/-2)
**Commit:** [pending — fill after commit]
