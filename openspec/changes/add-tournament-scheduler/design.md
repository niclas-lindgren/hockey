# Tournament Scheduler Design

## Context
First implementation of the hockey tournament scheduling system. No existing codebase. Need to choose technology stack and architecture that balances simplicity with functionality requirements (web scraping, Excel parsing, date analysis).

## Goals / Non-Goals
**Goals:**
- Simple, single-file implementation initially
- Reliable web scraping of Kongsberg Hall calendars
- Accurate conflict detection across multiple sources
- Clear output of available dates

**Non-Goals:**
- Web UI (CLI only for v1)
- Database persistence (in-memory processing)
- Real-time monitoring of calendar changes
- Automated booking integration

## Decisions

### Language: Python
**Why:**
- Excellent web scraping libraries (BeautifulSoup4, requests)
- Strong Excel support (openpyxl, pandas)
- Built-in datetime handling
- Fast prototyping for < 100 lines goal
- Rich ecosystem for Norwegian holidays (holidays library)

**Alternatives considered:**
- Node.js: Good scraping (cheerio) but weaker Excel handling
- Go: More verbose for this use case, limited scraping libraries

### Architecture: Single Script
Initial implementation as single Python script with functions:
- `scrape_ice_hall_calendar()` - fetch hockey tournaments
- `scrape_ball_hall_calendar()` - fetch wardrobe conflicts
- `parse_excel_schedule()` - read existing tournament dates
- `get_norwegian_holidays()` - identify public holiday weeks
- `filter_team_conflicts()` - exclude dates with team schedules
- `find_available_weekends()` - main analysis logic
- `main()` - CLI entry point

### Libraries
- `requests` - HTTP client for web scraping
- `beautifulsoup4` - HTML parsing
- `openpyxl` - Excel file reading
- `holidays` - Norwegian public holiday detection
- Built-in: `argparse`, `datetime`, `json`

### Data Flow
1. Fetch and parse ice hall calendar → List[Event]
2. Fetch and parse ball hall calendar → List[Event]
3. Parse Excel file (if provided) → List[Date]
4. Get Norwegian holidays for date range → List[Date]
5. Filter team conflicts from ice hall events → List[Date]
6. Combine all excluded dates
7. Generate weekend candidates (Sat/Sun only)
8. Filter out excluded dates and holiday weeks
9. Output sorted list of available weekends

### Web Scraping Strategy
- Target URL: `https://kongsberghallen.no/webkalender/ishall/` and `/ballhall-dagtid-og-helg/`
- Parse event data from calendar HTML structure
- Extract: event name, date, time
- Handle pagination if calendar spans multiple months
- Graceful error handling for network failures

### CLI Interface
```bash
python tournament_scheduler.py \
  --teams "Team A,Team B,Team C" \
  --excel-file existing_tournaments.xlsx \
  --start-date 2025-01-01 \
  --end-date 2025-12-31
```

## Risks / Trade-offs

**Risk: Website structure changes break scraping**
- Mitigation: Clear error messages, consider adding CSS selector tests

**Risk: Calendar pagination not handled**
- Mitigation: Initial implementation fetches visible month, expand if needed

**Trade-off: No date persistence**
- Accept: Rerun script when needed, keeps implementation simple

**Trade-off: Norwegian-specific logic hardcoded**
- Accept: Project is for Kongsberg Hall, no internationalization needed

## Migration Plan
N/A - New implementation, no existing system to migrate from.

## Open Questions
- Should the script output JSON format for integration with other tools?
- What date range should be default (next 6 months, 12 months, custom)?
- Should we handle multi-day tournaments spanning Sat-Sun as single slot?
