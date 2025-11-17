# Tournament Scheduling

## ADDED Requirements

### Requirement: Ice Hall Calendar Scraping
The system SHALL scrape and parse the Kongsberg Hall ice hall calendar from `https://kongsberghallen.no/webkalender/ishall/` to extract hockey tournament dates and team names.

#### Scenario: Successfully scrape ice hall events
- **WHEN** the ice hall calendar URL is accessible
- **THEN** the system extracts event names, dates, and times
- **AND** identifies which teams are participating in each event

#### Scenario: Handle ice hall scraping failure
- **WHEN** the ice hall calendar URL is unavailable or returns an error
- **THEN** the system logs the error and continues with available data sources

### Requirement: Ball Hall Calendar Scraping
The system SHALL scrape and parse the Kongsberg Hall ball hall calendar from `https://kongsberghallen.no/webkalender/ballhall-dagtid-og-helg/` to identify dates when wardrobes are inaccessible.

#### Scenario: Successfully scrape ball hall events
- **WHEN** the ball hall calendar URL is accessible
- **THEN** the system extracts event dates that make wardrobes unavailable

#### Scenario: Handle ball hall scraping failure
- **WHEN** the ball hall calendar URL is unavailable
- **THEN** the system logs the error and continues with available data sources

### Requirement: Excel Schedule Parsing
The system SHALL optionally accept an Excel file containing existing tournament dates and exclude those dates from suggestions.

#### Scenario: Parse valid Excel file
- **WHEN** an Excel file path is provided via CLI
- **THEN** the system reads tournament dates from the spreadsheet
- **AND** adds those dates to the exclusion list

#### Scenario: Handle missing Excel file
- **WHEN** the Excel file path does not exist
- **THEN** the system reports an error and exits

#### Scenario: Excel file not provided
- **WHEN** no Excel file is specified
- **THEN** the system proceeds without Excel-based exclusions

### Requirement: Team Schedule Filtering
The system SHALL accept a list of team names and exclude dates where those teams already have scheduled games in the ice hall calendar.

#### Scenario: Filter dates by team commitments
- **WHEN** team names are provided via CLI
- **THEN** the system identifies all dates where any of those teams have ice hall events
- **AND** excludes those dates from available weekend suggestions

#### Scenario: No team filter provided
- **WHEN** no team names are specified
- **THEN** the system does not filter by team commitments

### Requirement: Weekend-Only Suggestions
The system SHALL suggest only weekend dates (Saturday and Sunday) for tournament scheduling.

#### Scenario: Generate weekend candidates
- **WHEN** analyzing available dates within the specified range
- **THEN** the system considers only Saturdays and Sundays
- **AND** excludes all weekday dates

### Requirement: Public Holiday Avoidance
The system SHALL exclude weekends that fall within weeks containing Norwegian public holidays.

#### Scenario: Exclude holiday weeks
- **WHEN** a weekend falls in a week with a Norwegian public holiday
- **THEN** the system excludes that weekend from suggestions

#### Scenario: Include non-holiday weeks
- **WHEN** a weekend does not fall in a week with a public holiday
- **THEN** the system includes that weekend as a candidate

### Requirement: Date Range Specification
The system SHALL accept start and end dates via CLI to define the analysis period.

#### Scenario: Custom date range provided
- **WHEN** start date and end date are specified
- **THEN** the system analyzes only weekends within that range

#### Scenario: Default date range
- **WHEN** no date range is specified
- **THEN** the system uses the next 6 months as the analysis period

### Requirement: Available Date Output
The system SHALL output a sorted list of available weekend dates with conflict information.

#### Scenario: Display available weekends
- **WHEN** available dates are found
- **THEN** the system outputs dates in chronological order
- **AND** indicates why other dates were excluded (tournament conflict, wardrobe unavailable, team conflict, holiday week)

#### Scenario: No available dates found
- **WHEN** all weekends in the range are excluded
- **THEN** the system reports that no suitable dates were found
- **AND** provides a summary of exclusion reasons
