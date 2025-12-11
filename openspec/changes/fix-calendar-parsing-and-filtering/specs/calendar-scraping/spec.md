# Calendar Scraping

## MODIFIED Requirements

### REQ-CS-001: Parse Event Times Correctly

The calendar scraper must parse event start times from aria-labels and apply them to the datetime objects.

**Priority:** Critical
**Status:** Modified

**Changes:**
- Added logic to apply parsed `start_time` to event datetime instead of leaving it at midnight (00:00)
- Converts fractional hour values to hour and minute components before applying to datetime

**Rationale:** Without this fix, all events appear to start at 00:00 regardless of their actual time, causing incorrect conflict detection.

#### Scenario: Parse AM/PM formatted event times
**Given** an Outlook calendar event with aria-label "Event Name, 1:00 PM to 3:30 PM, Saturday, February 7, 2026, Busy"
**When** the scraper parses this event
**Then** the event datetime should be set to 13:00 (1:00 PM)
**And** the duration should be 2.5 hours

#### Scenario: Parse 24-hour formatted event times
**Given** an Outlook calendar event with aria-label "Event Name, 13:00 to 15:30, Saturday, February 7, 2026, Busy"
**When** the scraper parses this event
**Then** the event datetime should be set to 13:00
**And** the duration should be 2.5 hours

#### Scenario: All-day events remain at midnight
**Given** an Outlook calendar event with no time information in the aria-label
**When** the scraper parses this event
**Then** the event datetime should remain at 00:00 (midnight)
**And** the duration should be 0 hours
