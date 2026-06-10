# Plan: Season-plan interactive flow
**Goal:** Season-plan generation is accessible from the interactive Norwegian CLI flow, saves to history, and surfaces all warnings and rules report.
**Created:** 2026-06-10
**Intent:** The interactive flow already existed but lacked history saving, complete warning output, and rules report display.
**Backlog-ref:** 6

## Notes
The interactive season-plan flow was already implemented (menu option 3). Changes made:
- Fixed pre-existing syntax error (double comma in ask_yes_no)
- Added `history_manager.save_search()` after season plan generation
- Added `search_history.py` support for season plan entries in history display
- Added routing in `main()` so history-loaded season plans use `run_season_plan` instead of `run_search`
- Added hosting_warnings, month_load_warnings, rules_report, and game_count output to interactive flow
- Pass `rules_report` to Excel export in interactive flow

## Acceptance Criteria
- [ ] Interactive mode "Generer full sesongplan" (option 3) saves to search history.
- [ ] Season plan history entries show as "Sesongplan" in history display.
- [ ] Loading a season plan from history routes to the season plan flow.
- [ ] All warnings (hosting, month-load, game-count) and rules report are displayed.
- [ ] Existing tests pass (no regressions).

## Log
