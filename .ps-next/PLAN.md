# Plan: Age-group-aware hosting fairness
**Goal:** Compute host assignment targets and hosting fairness diagnostics per age group so unrelated teams do not inflate another age group's hosting responsibility.
**Created:** 2026-06-15
**Intent:** RVV organizers need host-load expectations they can explain from the teams participating in each aldersgruppe, not from a club's total roster elsewhere.
**Backlog-ref:** 101

## Tasks
- [x] Add age-group-aware host targets in the planner
  - Files: tournament_scheduler/season_planner.py, tests/test_season_planner.py
  - Approach: Change host assignment to receive scheduled `(date, age_group)` entries and allocate each age group's tournaments among clubs with teams in that age group using largest-remainder proportional targets. Add helper(s) for per-age expected/actual hosting details and tests proving adding/removing U10 teams does not increase U7 hosting expectation.
- [x] Update hosting fairness diagnostics and reports
  - Files: tournament_scheduler/season_planner.py, tournament_scheduler/html/html_exporter.py, tests/test_stage4_export.py
  - Approach: Use the per-age hosting breakdown in `_build_fairness_gate` and `_scan_hosting_warnings`; include concise per-age expected-vs-actual detail in metric metadata so HTML/report actions explain which age group/club caused a warning.
- [x] Run targeted and standard checks, then archive
  - Files: .ps-next/VERIFY.md, .ps-next/PLAN.md
  - Approach: Run targeted planner/export tests plus the repo quality gate. If unrelated pre-existing full-suite failures remain, record them with evidence and verify the acceptance criteria using targeted assertions.

## Notes
- Backlog item 101 follows item 100's hosting fairness review and asks for age-group-aware hosting assignment/fairness rather than total-team proportional targets.
- Current `_assign_hosts` uses total club team counts across the whole roster, and `_build_fairness_gate`/`_scan_hosting_warnings` compute expected hosting from total club team share.
- Full pytest was failing before this plan in two planner/stage3 tests that generate no plan for small/duplicate-label cases; avoid conflating those with this change.

## Acceptance Criteria
- [ ] Expected host counts are explainable per age group.
- [ ] Removing or adding U10 teams does not increase U7 hosting expectation.
- [ ] Tests show Kongsberg/Jar/Frisk-style host counts align with per-age rosters rather than total club roster size.
- [ ] Fairness report includes per-age expected vs actual hosting breakdown.
- [ ] `pytest tests/test_season_planner.py tests/test_stage4_export.py -q` passes.

## Log



### 2026-06-15 — Run targeted and standard checks, then archive
**Done:** Ran the targeted acceptance tests and the standard quality gate; recorded the remaining unrelated full-suite failure for verification.
**Rationale:** The targeted planner/export suite proves this hosting-fairness change, while the standard gate exposes a separate Stage 3 small-roster test fixture failure that predates this plan.
**Findings:** `pytest tests/test_season_planner.py tests/test_stage4_export.py -q` passed with 81 tests. `python3 -m pytest -q` fails only `tests/test_stage3_planning.py::TestRunStage3::test_duplicate_labels_are_disambiguated_in_counts` because that fixture has two teams per age group and Stage 3 now rejects <3-team tournaments.
**Files:** .ps-next/PLAN.md; .ps-next/VERIFY.md
**Commit:** not committed
### 2026-06-15 — Update hosting fairness diagnostics and reports
**Done:** Reworked hosting deviation diagnostics to use per-age expected-vs-actual rows, exposed them in fairness metric metadata, rendered a per-age hosting breakdown table in the HTML report, and added regression coverage.
**Rationale:** The report now explains host load from each age group's roster instead of total club roster share, making warnings actionable for organizers.
**Findings:** `pytest tests/test_season_planner.py -q` and `pytest tests/test_stage4_export.py -q` pass. Plan drift warning is expected because task 1 test changes remain in the working diff and CSS was updated to style the new report table.
**Files:** tournament_scheduler/season_planner.py; tournament_scheduler/html/html_exporter.py; tournament_scheduler/html/templates/styles.css; tests/test_season_planner.py; tests/test_stage4_export.py
**Commit:** not committed
### 2026-06-15 — Add age-group-aware host targets in the planner
**Done:** Changed host assignment to allocate hosts from per-age-group roster targets and added regression tests proving U10 roster changes do not alter U7 host targets or U7 assignments.
**Rationale:** Per-age host targets prevent clubs with many teams in unrelated age groups from being assigned extra hosting responsibility for smaller age groups.
**Findings:** Targeted proportional-hosting tests pass, including the updated small-age-group hosting_warnings property test.
**Files:** tournament_scheduler/season_planner.py; tests/test_season_planner.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
