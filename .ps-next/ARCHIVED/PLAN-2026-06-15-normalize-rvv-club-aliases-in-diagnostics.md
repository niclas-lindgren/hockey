# Plan: Normalize RVV club aliases in diagnostics
**Goal:** Season-plan report diagnostics treat common club-name aliases (for example `Sandefjord` and `Sandefjord Penguins`) as the same RVV club when evaluating missing hosts.
**Created:** 2026-06-15
**Intent:** Prevent false warning noise in the advisory report when planner/export data uses a short club name while the canonical RVV list uses the full display name.
**Backlog-ref:** 93

## Tasks
- [x] Add canonical club alias normalization for HTML report diagnostics
  - Files: tournament_scheduler/html/html_exporter.py
  - Approach: Introduce a small canonical-name helper/map near `_RVV_CLUBS`, use it in `_review_summary_html` when accumulating host counts and host sequence, and preserve display names in advisory text.
- [x] Add regression coverage for Sandefjord alias handling
  - Files: tests/test_stage4_export.py
  - Approach: Add a focused test that builds a plan whose host is `Sandefjord`, exports the report, and asserts the missing-host warning does not list `Sandefjord Penguins` while other existing report diagnostics still render.

## Notes
- The current advisory summary in `tournament_scheduler/html/html_exporter.py` compares `tournament.host_club` directly to `_RVV_CLUBS`, so `Sandefjord` is distinct from canonical `Sandefjord Penguins`.
- Keep normalization local and explicit for diagnostics; do not change serialized tournament host names or planner behavior.
- Existing tests in `tests/test_stage4_export.py` already assert the report contains the `Manglende klubber` diagnostic section.

## Acceptance Criteria
- [ ] `Sandefjord` host-club data is counted as `Sandefjord Penguins` for missing-host diagnostics.
- [ ] Generated `season_plan_report.html` no longer reports `Sandefjord Penguins` as missing when a tournament is hosted by `Sandefjord`.
- [ ] Regression tests pass for the affected export/report behavior.

## Log


### 2026-06-15 — Add regression coverage for Sandefjord alias handling
**Done:** Added a Stage 4 HTML export regression where all RVV clubs host and Sandefjord appears via the short alias; the report now passes missing-host diagnostics.
**Rationale:** The test locks down the user-visible report behavior that caused false missing-host warnings.
**Findings:** `pytest tests/test_stage4_export.py -q` passed (14 tests); quick quality gate passed full pytest suite (381 passed, 1 skipped).
**Files:** tests/test_stage4_export.py (+60/-1)
**Commit:** not committed
### 2026-06-15 — Add canonical club alias normalization for HTML report diagnostics
**Done:** Added explicit RVV club alias canonicalization for report diagnostics and applied it when collecting advisory host counts/sequence.
**Rationale:** The missing-host check should compare canonical RVV club identities rather than raw host strings, while leaving exported schedule data unchanged.
**Findings:** Current false warning came from direct string comparison between `Sandefjord` and `_RVV_CLUBS` canonical `Sandefjord Penguins`; also normalized `Tonsberg`/`Tønsberg` spelling variants.
**Files:** tournament_scheduler/html/html_exporter.py (+18/-2)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
