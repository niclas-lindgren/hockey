# Add Tournament Scheduler

## Why
Hockey tournament organizers need to find optimal weekend dates that avoid conflicts with other tournaments, wardrobe unavailability, existing team schedules, and public holidays. Manual checking across multiple calendars and sources is time-consuming and error-prone.

## What Changes
- Add web scraping capability for Kongsberg Hall calendars (ice hall and ball hall)
- Add tournament date conflict detection and analysis
- Add Excel file parsing for existing tournament schedules
- Add Norwegian public holiday detection
- Add team schedule filtering based on existing commitments
- Add weekend-only date suggestion logic
- Create command-line interface for tournament scheduling

## Impact
- Affected specs: `tournament-scheduling` (new capability)
- Affected code: New project - will create initial codebase
- External dependencies: Web scraping library, Excel parser, HTTP client, Norwegian holiday calendar
