# Tasks: Add Tournament Rescheduling

## Phase 1: Foundation - Utilities & Testing Setup

### 1.1 Create project structure for refactored code
- [x] Create `tournament_scheduler/` package directory
- [x] Create `tournament_scheduler/__init__.py`
- [x] Create `tournament_scheduler/utils/` for utilities
- [x] Create `tournament_scheduler/data_sources/` for calendar sources
- [x] Create `tournament_scheduler/conflict_checkers/` for conflict logic
- [x] Create `tests/` directory with subdirectories matching source structure
- [x] Add pytest configuration in `pytest.ini`

**Validation**: ✓ Directory structure exists, imports work

**Dependencies**: None (can run immediately)

---

### 1.2 Implement DateParser utility
- [x] Create `tournament_scheduler/utils/date_parser.py`
- [x] Implement `DateParser.parse()` with support for DD.MM.YYYY, DD/MM/YYYY, YYYY-MM-DD
- [x] Implement `DateParser.parse_datetime_cell()` for Excel datetime objects
- [x] Add comprehensive unit tests in `tests/utils/test_date_parser.py`
- [x] Test edge cases: None, empty strings, invalid formats, leap years

**Validation**: ✓ All tests pass, 100% coverage for DateParser

**Dependencies**: 1.1

---

### 1.3 Replace existing date parsing with DateParser
- [x] Identify all date parsing locations in `tournament_scheduler.py` (6+ instances)
- [x] Import DateParser in `tournament_scheduler.py`
- [x] Replace date parsing in `parse_excel_schedule()`
- [x] Replace date parsing in `filter_team_conflicts()`
- [x] Replace date parsing in `find_available_weekends()` (3 locations)
- [x] Run existing CLI commands to verify no regression
- [x] Verify output matches previous implementation

**Validation**: ✓ All existing functionality works, no behavior changes

**Dependencies**: 1.2

---

## Phase 2: Data Models & Interfaces

### 2.1 Create data models
- [x] Create `tournament_scheduler/models.py`
- [x] Define `CalendarEvent` dataclass with: date, name, datetime, duration_hours
- [x] Define `TournamentInfo` dataclass with: date, name, teams, location
- [x] Define `ConflictContext` dataclass with all conflict checking context
- [x] Define `ConflictResult` dataclass with: excluded_dates, reasons, checker_name
- [x] Define `SchedulingResult` dataclass with: available_dates, exclusion_breakdown, etc.
- [x] Add type hints to all dataclasses
- [x] Create unit tests for dataclass validation

**Validation**: ✓ Models instantiate correctly, type checking passes

**Dependencies**: 1.1

---

### 2.2 Create abstract interfaces
- [x] Create `tournament_scheduler/interfaces.py`
- [x] Define `CalendarDataSource` ABC with `fetch_events()` and `get_source_name()`
- [x] Define `ConflictChecker` ABC with `check_conflicts()` and `get_checker_name()`
- [x] Add type hints using models from 2.1
- [x] Document interface contracts in docstrings
- [x] Create mock implementations for testing

**Validation**: ✓ Interfaces define clear contracts, can instantiate mocks

**Dependencies**: 2.1

---

## Phase 3: Calendar Data Sources

### 3.1 Extract calendar scraping to CalendarScraper
- [x] Create `tournament_scheduler/data_sources/calendar_scraper.py`
- [x] Extract `scrape_calendar_with_playwright()` logic to `CalendarScraper` class
- [x] Extract `parse_outlook_calendar_text()` as instance method
- [x] Add error handling and logging
- [x] Create tests with mocked Playwright responses
- [x] Test month navigation logic
- [x] Test event deduplication

**Validation**: Scraper works with cached Playwright responses

**Dependencies**: 2.1, 2.2

---

### 3.2 Implement IceHallCalendar
- [x] Create `tournament_scheduler/data_sources/ice_hall_calendar.py`
- [x] Implement `IceHallCalendar(CalendarDataSource)`
- [x] Move `is_tournament_event()` logic into class
- [x] Implement `fetch_events()` using CalendarScraper
- [x] Filter for tournament events only
- [x] Add unit tests with mock scraper
- [x] Test tournament keyword detection

**Validation**: IceHallCalendar returns only tournament events

**Dependencies**: 2.2, 3.1

---

### 3.3 Implement BallHallCalendar
- [x] Create `tournament_scheduler/data_sources/ball_hall_calendar.py`
- [x] Implement `BallHallCalendar(CalendarDataSource)`
- [x] Add `min_duration` parameter (default 2.0 hours)
- [x] Implement `fetch_events()` using CalendarScraper
- [x] Filter events by duration threshold
- [x] Add unit tests with various durations
- [x] Test duration parsing edge cases

**Validation**: BallHallCalendar returns only events >2 hours

**Dependencies**: 2.2, 3.1

---

## Phase 4: Excel Reading & Team Extraction

### 4.1 Implement ExcelTournamentReader
- [x] Create `tournament_scheduler/excel/tournament_reader.py`
- [x] Implement `ExcelTournamentReader` class
- [x] Implement `get_all_tournament_dates()` - scan for datetime cells
- [x] Implement `get_tournament_info(date)` - extract tournament details
- [x] Implement `extract_teams_for_date(date)` - find team list for date
- [x] Handle various Excel layouts (robust parsing)
- [x] Add logging for debugging Excel structure
- [x] Handle missing dates gracefully with clear errors

**Validation**: Can extract teams from sample Excel file

**Dependencies**: 1.2, 2.1

---

### 4.2 Create comprehensive tests for Excel reader
- [x] Create `tests/fixtures/sample_tournament.xlsx` with known structure
- [x] Test extracting all tournament dates
- [x] Test extracting teams for specific date
- [x] Test error handling for missing date
- [x] Test various Excel layouts
- [x] Test empty team lists
- [x] Test malformed Excel files
- [x] Verify error messages are clear

**Validation**: All Excel parsing tests pass, handles edge cases

**Dependencies**: 4.1

---

## Phase 5: Conflict Checkers

### 5.1 Implement HolidayConflictChecker
- [x] Create `tournament_scheduler/conflict_checkers/holiday_checker.py`
- [x] Implement `HolidayConflictChecker(ConflictChecker)`
- [x] Extract holiday logic from `get_norwegian_holidays()`
- [x] Implement `check_conflicts()` returning ConflictResult
- [x] Include holiday names in exclusion reasons
- [x] Add tests for Norwegian holidays
- [x] Test week-surrounding logic

**Validation**: Correctly identifies holiday weeks

**Dependencies**: 2.1, 2.2

---

### 5.2 Implement TournamentConflictChecker
- [x] Create `tournament_scheduler/conflict_checkers/tournament_checker.py`
- [x] Implement `TournamentConflictChecker(ConflictChecker)`
- [x] Accept IceHallCalendar as dependency
- [x] Implement `check_conflicts()` for tournament dates
- [x] Include tournament names in reasons
- [x] Add tests with mock calendar data
- [x] Test event filtering

**Validation**: Correctly identifies tournament conflicts

**Dependencies**: 2.1, 2.2, 3.2

---

### 5.3 Implement BallHallConflictChecker
- [x] Create `tournament_scheduler/conflict_checkers/ball_hall_checker.py`
- [x] Implement `BallHallConflictChecker(ConflictChecker)`
- [x] Accept BallHallCalendar as dependency
- [x] Implement `check_conflicts()` for ball hall events
- [x] Include event names and durations in reasons
- [x] Add tests with various durations
- [x] Test duration threshold

**Validation**: Correctly identifies ball hall conflicts

**Dependencies**: 2.1, 2.2, 3.3

---

### 5.4 Implement TeamAvailabilityChecker
- [x] Create `tournament_scheduler/conflict_checkers/team_availability_checker.py`
- [x] Implement `TeamAvailabilityChecker(ConflictChecker)`
- [x] Implement `check_team_availability(team, dates)` helper
- [x] Implement `check_conflicts()` checking all teams in context
- [x] Use case-insensitive substring matching for team names
- [x] Include conflicting team and event in reasons
- [x] Add tests with various team name formats
- [x] Test with multiple teams, partial matches

**Validation**: Correctly identifies team conflicts

**Dependencies**: 2.1, 2.2, 3.2

---

### 5.5 Implement ExcelConflictChecker
- [x] Create `tournament_scheduler/conflict_checkers/excel_checker.py`
- [x] Implement `ExcelConflictChecker(ConflictChecker)`
- [x] Accept excel_dates Set as dependency
- [x] Implement `check_conflicts()` for Excel exclusions
- [x] Add tests with various date sets
- [x] Test empty date set

**Validation**: Correctly excludes Excel dates

**Dependencies**: 2.1, 2.2

---

## Phase 6: Orchestration Layer

### 6.1 Implement TournamentScheduler orchestrator
- [x] Create `tournament_scheduler/scheduler.py`
- [x] Implement `TournamentScheduler` class
- [x] Accept calendar_sources, conflict_checkers, date_parser as dependencies
- [x] Implement `_get_weekend_dates(start, end)` helper
- [x] Implement `_aggregate_conflict_results(results)` helper
- [x] Implement `find_available_dates()` method
- [x] Coordinate all components
- [x] Add comprehensive integration tests

**Validation**: Finds available dates using all checkers

**Dependencies**: 2.1, 2.2, 5.1-5.5

---

### 6.2 Implement reschedule_tournament method
- [x] Add `reschedule_tournament()` to TournamentScheduler
- [x] Use ExcelTournamentReader to extract teams
- [x] Build ConflictContext with tournament teams
- [x] Call find_available_dates with team context
- [x] Return SchedulingResult with tournament info
- [x] Add integration tests for rescheduling
- [x] Test with real Excel file from fixtures

**Validation**: Successfully reschedules tournaments

**Dependencies**: 6.1, 4.1, 5.4

---

## Phase 7: CLI Integration

### 7.1 Add reschedule CLI arguments
- [x] Update argument parser in `tournament_scheduler.py`
- [x] Add `--reschedule` argument accepting date in YYYY-MM-DD format
- [x] Validate reschedule date format
- [x] Validate excel-file is required when reschedule is specified
- [x] Add helpful error messages
- [x] Update help text with examples
- [x] Test CLI argument parsing

**Validation**: CLI accepts and validates reschedule arguments

**Dependencies**: None (can run in parallel with Phase 6)

---

### 7.2 Wire up new architecture in main()
- [x] Instantiate DateParser in main()
- [x] Instantiate CalendarScraper with Playwright config
- [x] Instantiate IceHallCalendar and BallHallCalendar
- [x] Instantiate all ConflictCheckers
- [x] Instantiate TournamentScheduler with dependencies
- [x] Update existing code path to use new scheduler
- [x] Verify all existing functionality still works
- [x] Test with various CLI argument combinations

**Validation**: Existing functionality preserved, no regressions

**Dependencies**: 6.1, 7.1

---

### 7.3 Implement reschedule CLI flow
- [x] Add conditional logic for reschedule mode in main()
- [x] Parse reschedule date from CLI args
- [x] Validate Excel file exists
- [x] Call scheduler.reschedule_tournament()
- [x] Handle errors gracefully (date not found, no teams, etc.)
- [x] Display clear error messages
- [x] Test error cases

**Validation**: Reschedule mode triggers correctly from CLI

**Dependencies**: 6.2, 7.2

---

### 7.4 Update output formatting for rescheduling
- [x] Create `format_rescheduling_output()` function
- [x] Display "RESCHEDULING TOURNAMENT FROM [date]"
- [x] Show tournament name and teams
- [x] Show available alternative dates
- [x] Show exclusion breakdown with team availability
- [x] Indicate dates closest to original
- [x] Add helpful suggestions if no dates found
- [x] Test output formatting with various scenarios

**Validation**: Rescheduling output is clear and informative

**Dependencies**: 7.3

---

## Phase 8: Testing & Quality

### 8.1 Create integration test suite
- [x] Create `tests/integration/test_scheduling_flow.py`
- [x] Test end-to-end scheduling with cached calendar data
- [x] Test end-to-end rescheduling with fixture Excel file
- [x] Test all conflict types in combination
- [x] Test edge cases (no available dates, all teams conflict)
- [x] Mock Playwright to avoid network calls
- [x] Verify performance (complete in <5 seconds with mocks)

**Validation**: All integration tests pass

**Dependencies**: All previous phases

---

### 8.2 Add code quality checks
- [x] Set up pytest with coverage reporting
- [x] Configure coverage target: >80%
- [x] Add complexity checking (radon or similar)
- [x] Set complexity threshold: <10
- [x] Add type checking with mypy
- [x] Fix all type errors
- [x] Verify no code duplication (DRY)
- [x] Create pre-commit hook configuration

**Validation**: Coverage >80%, complexity <10, type checking passes

**Dependencies**: 8.1

---

### 8.3 Manual testing scenarios
- [x] Test rescheduling with real Excel file: `./existing_schedule/U10_ETTER_JUL_Klar_-_Kongsberg_Sandefjord.xlsx`
- [x] Verify teams extracted correctly for known date
- [x] Compare team availability results with manual calendar check
- [x] Test with date not in Excel (error handling)
- [x] Test with date range too narrow (no alternatives)
- [x] Test with wide date range (many alternatives)
- [x] Verify all existing CLI options still work
- [x] Performance test with real calendar scraping

**Validation**: Manual testing confirms correct behavior

**Dependencies**: 7.4

---

## Phase 9: Documentation & Cleanup

### 9.1 Update README with rescheduling examples
- [x] Add "Rescheduling Tournaments" section to README
- [x] Add basic rescheduling example
- [x] Add example output showing teams and alternatives
- [x] Document new CLI arguments
- [x] Add troubleshooting section
- [x] Update requirements section if needed
- [x] Add architecture diagram to docs

**Validation**: README is clear and complete

**Dependencies**: 8.3

---

### 9.2 Create developer documentation
- [x] Create `ARCHITECTURE.md` documenting design
- [x] Document SOLID principles used
- [x] Document how to add new conflict checkers
- [x] Document how to add new calendar sources
- [x] Create class diagram
- [x] Add code examples for common tasks
- [x] Document testing strategy

**Validation**: Developer docs enable extending the system

**Dependencies**: 8.3

---

### 9.3 Add docstrings and type hints
- [x] Add comprehensive docstrings to all public classes
- [x] Add docstrings to all public methods
- [x] Document parameters and return types
- [x] Add usage examples in docstrings
- [x] Verify all functions have type hints
- [x] Run mypy strict mode
- [x] Fix any typing issues

**Validation**: All public APIs documented, mypy strict passes

**Dependencies**: All implementation phases

---

### 9.4 Clean up old code
- [x] Remove old commented-out code
- [x] Remove unused imports
- [x] Remove duplicate helper functions
- [x] Ensure consistent code style
- [x] Run black formatter
- [x] Run isort for imports
- [x] Final code review

**Validation**: Codebase is clean and consistent

**Dependencies**: 9.3

---

## Phase 10: Validation & Deployment

### 10.1 Run full test suite
- [x] Run all unit tests
- [x] Run all integration tests
- [x] Verify >80% coverage
- [x] Run type checking
- [x] Run complexity checks
- [x] Run linters
- [x] Fix any issues found

**Validation**: All tests pass, quality metrics met

**Dependencies**: All previous phases

---

### 10.2 Performance validation
- [x] Measure calendar scraping time
- [x] Measure conflict checking time
- [x] Measure total execution time
- [x] Verify performance is acceptable (<2 min with real scraping)
- [x] Profile for bottlenecks if needed
- [x] Optimize if necessary

**Validation**: Performance meets requirements

**Dependencies**: 10.1

---

### 10.3 Create example usage scripts
- [x] Create `examples/reschedule_example.sh` with real commands
- [x] Create `examples/find_available_dates.sh`
- [x] Add sample Excel file to examples/
- [x] Document expected output
- [x] Test all example scripts

**Validation**: Examples run successfully

**Dependencies**: 10.1

---

### 10.4 Final validation
- [x] Review all specs are implemented
- [x] Review all requirements are met
- [x] Verify SOLID principles followed
- [x] Verify DRY principles followed
- [x] Run openspec validate --strict
- [x] Fix any validation issues
- [x] Get code review approval

**Validation**: OpenSpec validation passes, code review approved

**Dependencies**: All previous tasks

---

## Summary

**Total Tasks**: 48
**Estimated Time**: 5-7 days
**Parallelizable**: Phases 1-2, Phase 7.1 can start early

**Critical Path**:
1.1 → 1.2 → 1.3 → 2.1 → 2.2 → 3.1 → 3.2 → 4.1 → 5.4 → 6.2 → 7.3 → 7.4 → 8.3 → 10.4

**Key Milestones**:
- Phase 3 Complete: Calendar sources refactored (Day 2)
- Phase 5 Complete: All conflict checkers implemented (Day 4)
- Phase 7 Complete: Rescheduling works from CLI (Day 5)
- Phase 10 Complete: Fully validated and documented (Day 7)
