# Spec: Tournament Rescheduling

## ADDED Requirements

### Requirement: CLI accepts reschedule parameters
The command-line interface SHALL accept tournament rescheduling parameters to identify and reschedule existing tournaments.

#### Scenario: User initiates tournament rescheduling
**Given** the user has an Excel file with scheduled tournaments
**And** a tournament needs to be rescheduled from its current date
**When** the user runs the command with `--reschedule 2026-01-17 --excel-file schedule.xlsx --start-date 2026-01-01 --end-date 2026-06-30`
**Then** the system SHALL accept the reschedule date in YYYY-MM-DD format
**And** the system SHALL require the excel-file parameter when reschedule is specified
**And** the system SHALL validate that the reschedule date exists as a valid date

#### Scenario: System validates reschedule parameters
**Given** the user specifies a reschedule date
**When** the excel-file parameter is missing
**Then** the system SHALL display an error message: "Excel file is required when using --reschedule"
**And** the system SHALL exit with non-zero status code

#### Scenario: Invalid reschedule date format
**Given** the user provides an invalid date format
**When** the user runs `--reschedule 17-01-2026`
**Then** the system SHALL display an error message indicating the correct format
**And** the system SHALL show usage example: "--reschedule 2026-01-17"

---

### Requirement: Extract teams from Excel tournament
The system SHALL parse Excel files to identify all teams participating in a tournament on a specific date.

#### Scenario: Extract teams for tournament date
**Given** an Excel file containing tournament schedules
**And** the tournament on 2026-01-17 includes teams "Frisk Asker 1", "Jar 3", "Kongsberg", "Sandefjord"
**When** the system extracts teams for date 2026-01-17
**Then** the system SHALL return all 4 teams
**And** the system SHALL preserve exact team names as they appear in Excel

#### Scenario: Tournament date not found in Excel
**Given** an Excel file with tournaments
**When** the system searches for a tournament on 2026-12-25
**And** no tournament exists on that date
**Then** the system SHALL display error: "No tournament found on 2026-12-25 in Excel file"
**And** the system SHALL list the available tournament dates in the file
**And** the system SHALL exit with non-zero status code

#### Scenario: Handle Excel files with different structures
**Given** Excel files may have varying layouts
**When** the system encounters a tournament section
**Then** the system SHALL identify the date row by searching for datetime cells
**And** the system SHALL extract team names from rows following the date
**And** the system SHALL stop extraction at the next tournament section or empty rows
**And** the system SHALL filter out header rows and non-team entries

#### Scenario: Empty team list
**Given** an Excel file with a tournament date
**When** no teams are listed for that tournament
**Then** the system SHALL display warning: "No teams found for tournament on [date]"
**And** the system SHALL exit with non-zero status code

---

### Requirement: Check team availability
The system SHALL verify that all tournament teams are available on candidate dates by checking their schedules against calendar events.

#### Scenario: All teams available on date
**Given** a tournament with teams ["Kongsberg", "Frisk Asker 1", "Jar 3"]
**When** checking availability for 2026-02-15
**And** none of the teams have events on that date
**Then** the system SHALL mark 2026-02-15 as available for all teams
**And** the date SHALL pass the team availability check

#### Scenario: One team has conflict
**Given** a tournament with teams ["Kongsberg", "Frisk Asker 1", "Jar 3"]
**When** checking availability for 2026-02-22
**And** "Frisk Asker 1" has an event on 2026-02-22
**Then** the system SHALL mark 2026-02-22 as unavailable
**And** the exclusion reason SHALL indicate "Team conflict: Frisk Asker 1 - [Event Name]"

#### Scenario: Multiple teams have conflicts
**Given** a tournament with teams ["Kongsberg", "Sandefjord"]
**When** checking availability for 2026-03-01
**And** both "Kongsberg" and "Sandefjord" have events on that date
**Then** the system SHALL mark 2026-03-01 as unavailable
**And** the exclusion reason SHALL list all conflicting teams

#### Scenario: Team name matching
**Given** team names in Excel may be partial matches in calendar events
**When** checking calendar event "Kongsberg vs Oslo - Regional Cup"
**And** the tournament team is "Kongsberg"
**Then** the system SHALL match the team name case-insensitively
**And** the system SHALL detect the conflict

---

### Requirement: Find alternative dates for tournament
The system SHALL find available weekend dates when all tournament teams are free and all existing conflict checks pass.

#### Scenario: Find alternative dates with all checks
**Given** a tournament on 2026-01-17 with 4 teams
**When** searching for alternatives from 2026-02-01 to 2026-06-30
**Then** the system SHALL check each weekend date for:
  - All 4 teams are available
  - No ice hall tournament conflicts
  - No ball hall conflicts (>2 hours)
  - Not in Norwegian holiday weeks
  - Not in Excel exclusion list
**And** the system SHALL return only dates passing all checks

#### Scenario: Display rescheduling results
**Given** alternative dates have been found
**When** displaying results
**Then** the system SHALL show:
  - "RESCHEDULING TOURNAMENT FROM [original-date]"
  - "Teams: [team1], [team2], ..."
  - List of available alternative dates
  - Exclusion summary with team availability breakdown

#### Scenario: No alternative dates available
**Given** a tournament needs rescheduling
**When** no dates pass all checks in the date range
**Then** the system SHALL display: "No alternative dates found for all teams"
**And** the system SHALL show exclusion breakdown
**And** the system SHALL suggest expanding the date range

#### Scenario: Rank alternative dates
**Given** multiple alternative dates are available
**When** displaying results
**Then** the system SHALL order dates chronologically
**And** the system SHALL indicate proximity to original date
**And** the system SHALL show day of week for each date

---

## MODIFIED Requirements

### Requirement: Conflict checking is modular
The conflict checking system SHALL be implemented as independent, composable components that can be extended without modifying existing code.

#### Scenario: Add new conflict checker type
**Given** a new conflict source needs to be added
**When** a developer implements the ConflictChecker interface
**Then** the new checker SHALL integrate without modifying existing checkers
**And** the new checker SHALL receive ConflictContext with all needed data
**And** the new checker SHALL return ConflictResult with standardized format

#### Scenario: Conflict checkers run independently
**Given** multiple conflict checkers are configured
**When** checking date availability
**Then** each checker SHALL run independently
**And** failure in one checker SHALL NOT prevent others from running
**And** results SHALL be aggregated from all checkers

---

### Requirement: Date parsing is centralized
All date parsing logic SHALL be consolidated into a single DateParser utility to ensure consistency and eliminate duplication.

#### Scenario: Parse dates consistently across codebase
**Given** dates appear in various formats throughout the system
**When** any component needs to parse a date string
**Then** it SHALL use DateParser.parse()
**And** the parser SHALL attempt all supported formats: DD.MM.YYYY, DD/MM/YYYY, YYYY-MM-DD
**And** the parser SHALL return None for unparseable dates

#### Scenario: Handle Excel datetime cells
**Given** Excel cells contain datetime objects
**When** parsing Excel data
**Then** the system SHALL use DateParser.parse_datetime_cell()
**And** the parser SHALL handle both datetime objects and string representations

---

### Requirement: Architecture follows SOLID principles
The codebase SHALL be structured to follow SOLID principles for maintainability and extensibility.

#### Scenario: Single Responsibility Principle
**Given** any class in the system
**Then** the class SHALL have one clear responsibility
**And** the class name SHALL reflect that responsibility
**And** class methods SHALL support only that responsibility

**Examples**:
- DateParser: Only parses dates
- IceHallCalendar: Only fetches/parses ice hall data
- HolidayConflictChecker: Only checks holiday conflicts
- ExcelTournamentReader: Only reads Excel tournament data

#### Scenario: Open/Closed Principle
**Given** new functionality needs to be added
**When** implementing calendar sources or conflict checkers
**Then** new classes SHALL implement abstract interfaces
**And** existing classes SHALL NOT be modified
**And** new implementations SHALL be injected via dependency injection

#### Scenario: Dependency Inversion Principle
**Given** high-level scheduling logic
**Then** it SHALL depend on abstract interfaces (CalendarDataSource, ConflictChecker)
**And** it SHALL NOT depend on concrete implementations
**And** concrete implementations SHALL be injected via constructor

---

### Requirement: Code follows DRY principle
The codebase SHALL eliminate duplicate logic by extracting common functionality into reusable components.

#### Scenario: Date parsing not duplicated
**Given** date parsing occurs in multiple places
**Then** all date parsing SHALL use DateParser utility
**And** date format lists SHALL be defined once
**And** parsing logic SHALL NOT be copied

#### Scenario: Calendar scraping not duplicated
**Given** multiple calendars need scraping
**Then** common scraping logic SHALL be in CalendarScraper base
**And** calendar-specific logic SHALL be in subclasses
**And** Playwright setup SHALL NOT be duplicated

#### Scenario: Conflict checking not duplicated
**Given** multiple conflict types need checking
**Then** conflict checking framework SHALL be reusable
**And** each checker SHALL implement standard interface
**And** aggregation logic SHALL NOT be duplicated

---

## Implementation Notes

### Excel Parsing Strategy
To handle various Excel formats:
1. Scan for datetime cells (tournament dates)
2. Look for "Deltagende lag" (Participating teams) or team names in subsequent rows
3. Extract team names until next tournament section
4. Filter out headers, separators, empty rows

### Team Name Matching
- Case-insensitive substring matching
- Trim whitespace
- Handle common variations (abbreviations, numbers)
- Match team name anywhere in event title

### Performance Optimizations
- Cache calendar event data for date range
- Cache parsed Excel data
- Run conflict checkers in parallel where possible
- Use set operations for date filtering

### Error Handling
- Validate Excel file exists and is readable
- Handle malformed Excel structures gracefully
- Provide clear error messages for missing data
- Show available tournament dates when date not found

### Testing Requirements
- Unit tests for each component
- Integration tests for full rescheduling flow
- Test with various Excel formats
- Mock calendar responses for tests
- Test edge cases (no teams, all dates excluded, etc.)
