# Plan: Fix iCal Export — One VEVENT per Tournament

**Feature:** Fix iCal export to produce one VEVENT per tournament (not per match): each tournament event SUMMARY/DESCRIPTION should list the participating teams and round-robin matchups inside the description body, but the calendar entry itself represents the full tournament day — not individual games. Currently exporting one event per game produces unusable calendar spam.
**Goal:** Fix iCal export to produce one VEVENT per tournament (not per match): each tournament event SUMMARY/DESCRIPTION should list the participating teams and round-robin matchups inside the description body, but the calendar entry itself represents the full tournament day — not individual games. Currently exporting one event per game produces unusable calendar spam.
**Backlog-ref:** 167
**Constraints:** none
**Date:** 2026-06-20
**Intent:** Replace the per-game VEVENT spam in the pipeline iCal export with a single per-tournament event that includes teams and matchup pairings in the description, making the calendar output usable.

---

## Tasks

- [x] Changed iCal export call in stage4_export.py from export() to export_tournament_summary() so the pipeline produces one VEVENT per tournament. — 2026-06-20
  - **Files:** `tournament_scheduler/pipeline/stage4_export.py`
  - **Approach:** Change the iCal call at line 136 from `ICalExporter(...).export(plan, ical_path)` to `ICalExporter(...).export_tournament_summary(plan, ical_path)`. This is a one-line change at the call site that routes the pipeline through the already-existing per-tournament export method.

- [ ] Add round-robin matchup pairings to tournament summary event description
  - **Files:** `tournament_scheduler/ical/ical_exporter.py`
  - **Approach:** In `_tournament_summary_event()`, after building the existing `description_lines` (arena, age group, host, team list), append a "Kamper:" section by iterating `tournament.games` and formatting each as `"{game.home.label} vs {game.away.label}"`. Only append when `tournament.games` is non-empty.

- [ ] Write tests verifying one VEVENT per tournament and description content
  - **Files:** `tests/test_stage4_export.py`, `tests/test_ical_exporter.py` (create if not exists)
  - **Approach:** Add a test that builds a minimal SeasonPlan with two tournaments each having multiple games, calls `ICalExporter().export_tournament_summary()`, parses the resulting .ics, and asserts: (1) VEVENT count equals tournament count, not game count; (2) each VEVENT DESCRIPTION contains team names; (3) each VEVENT DESCRIPTION contains at least one "vs" pairing. Also add a test that calls `stage4_export.run()` and confirms the exported .ics contains the correct VEVENT count.

---

## Acceptance Criteria

The iCal export pipeline produces one VEVENT entry per tournament day instead of one VEVENT per game.
The iCal export output contains tournament summary information including participating teams and round-robin matchups in the DESCRIPTION field of each VEVENT.
Each tournament VEVENT in the exported .ics file has a SUMMARY field that identifies the tournament day and a DESCRIPTION field listing all participating teams and their matchups.
The iCal exporter produces valid .ics files that contain exactly one VEVENT per tournament rather than one VEVENT per individual match.
The pytest suite passes after the changes, with new tests confirming VEVENT count matches tournament count and description contains matchup pairings.

## Log
- 2026-06-20 Plan created for backlog item 167 — iCal one VEVENT per tournament fix

### 2026-06-20 — Changed iCal export call in stage4_export.py from export() to export_tournament_summary() so the pipeline produces one VEVENT per tournament.
**Rationale:** One-line change at the call site; the target method already existed in ICalExporter.
**Findings:** All 585 tests pass after the change.
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage4_export.py (+6/-3)
**Commit:** [pending — fill after commit]
