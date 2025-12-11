# Tournament Filtering

## MODIFIED Requirements

### REQ-TF-001: Use Filtered Calendar Sources

The tournament scheduler must use `IceHallCalendar.fetch_events()` to retrieve tournament events, ensuring non-tournament events are filtered out.

**Priority:** Critical
**Status:** Modified

**Changes:**
- Changed from calling `scraper.scrape_calendar()` directly to calling `calendar.fetch_events()`
- Ensures tournament keyword filtering is applied before events are used in conflict checking

**Rationale:** Bypassing the filtering layer causes non-tournament events like "Åpen ishall" (open ice) to block tournament dates incorrectly.

#### Scenario: Non-tournament events are filtered out
**Given** the Kongsberg ice hall calendar has events "EF søndag" and "Åpen ishall" on the same date
**When** fetching tournament events via `IceHallCalendar.fetch_events()`
**Then** "EF søndag" should be included (tournament event)
**And** "Åpen ishall" should be excluded (non-tournament event)

#### Scenario: Interactive scheduler uses filtered events
**Given** the interactive scheduler is checking Kongsberg ice hall availability
**When** building the `all_events_for_teams` list
**Then** it must call `kongsberg_ice.fetch_events()` not `outlook_scraper.scrape_calendar()`
**And** only tournament events should be included in conflict checking

### REQ-TF-002: Recognize Tournament Event Keywords

The ice hall calendar filter must recognize common tournament event patterns including team matches, age group games, and series events.

**Priority:** High
**Status:** Modified

**Changes:**
- Added 'ef ' to recognize Elite series events
- Added 'ju' to recognize junior events (JU14, JU15, etc.)
- Added 'kamp' to recognize match events
- Added age group identifiers (u8-u18) to recognize team-specific tournament games

**Rationale:** Events like "EF søndag" and "KAMP KIF U18" are tournaments but weren't being recognized by the previous keyword list.

#### Scenario: Recognize Elite series events
**Given** a calendar event named "EF søndag"
**When** checking if it's a tournament event
**Then** it should be recognized as a tournament (matches 'ef ')

#### Scenario: Recognize junior tournament matches
**Given** a calendar event named "KAMP JU14 - Lillehammer kl 1500"
**When** checking if it's a tournament event
**Then** it should be recognized as a tournament (matches 'ju' and 'kamp')

#### Scenario: Recognize age group matches
**Given** a calendar event named "KAMP KIF U18 - Gjøvik kl 1300"
**When** checking if it's a tournament event
**Then** it should be recognized as a tournament (matches 'u18' and 'kamp')

#### Scenario: Filter out practice and open ice events
**Given** calendar events named "Åpen Ishall" and "Rek.lag"
**When** checking if they are tournament events
**Then** both should be excluded (match non-tournament keywords)
