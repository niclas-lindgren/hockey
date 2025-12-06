# Hockey Tournament Scheduler

Find optimal weekend dates for hockey tournaments by analyzing conflicts from multiple sources.

## Features

### Core Functionality
- **Interactive Mode** - User-friendly guided interface (Norwegian language)
- **Search History** - Save and reuse previous searches
- Reschedule existing tournaments - Find alternative dates when all teams are available
- Find dates for new tournaments
- Weekend-only suggestions (Saturday and Sunday)

### Calendar Integration
- **Kongsberg ice hall** - Local tournament conflicts
- **Kongsberg ball hall** - Wardrobe availability (warnings only)
- **Skien ice hall** - External team conflicts (via Google Calendar iCal feed)

### Smart Conflict Detection
- Team availability across multiple calendars
- Norwegian public holidays (excludes weekends before holidays)
- Excel-based tournament schedules
- Same-day conflicts (blocks dates)
- Same-weekend conflicts (warnings with details)

### Time Slot Analysis
- Suggests earliest available start times (11:00-14:00 window)
- Requires minimum 2.5 hours for tournaments
- Shows all available time slots for each date
- Considers existing bookings from all calendars

## Installation

1. Create virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install chromium
```

## Usage

### Interactive Mode (Recommended)

The interactive mode provides a user-friendly guided experience:

```bash
./venv/bin/python3 tournament_scheduler_interactive.py
```

Features:
- **Norwegian language interface** - All prompts and output in Norwegian
- **Guided workflow** - Step-by-step questions for all parameters
- **Search history** - Automatically saves searches
  - Reuse previous searches without re-entering parameters
  - Browse up to 20 most recent searches
  - History stored in `~/.hockey_scheduler_history.json`
- **Smart defaults** - Suggests reasonable date ranges
- **Multiple calendar selection** - Choose which calendars to check
- **Detailed results** with:
  - Suggested time slots (earliest available)
  - Weekend conflict warnings
  - Team-specific conflict details

Example workflow:
1. Choose: Reschedule tournament or find new dates
2. Enter date range (defaults to 6 months)
3. If rescheduling: Provide Excel file and tournament date
4. Select calendars to check (Kongsberg ice/ball, Skien ice)
5. View results with suggested times and warnings
6. Search automatically saved to history

### Command-Line Mode

For automation or scripting, use the command-line interface:

Show help and examples:
```bash
./tournament-scheduler.sh --help
```

Basic usage:
```bash
./tournament-scheduler.sh --start-date 2025-01-01 --end-date 2025-06-30
```

Reschedule an existing tournament:
```bash
./tournament-scheduler.sh \
  --reschedule 2026-01-17 \
  --excel-file existing_schedule/tournament_schedule.xlsx \
  --start-date 2026-02-01 \
  --end-date 2026-06-30
```

Filter by team names:
```bash
./tournament-scheduler.sh --teams "Kongsberg,Drammen,Oslo" --start-date 2025-01-01
```

## Command-Line Options

- `--teams` - Comma-separated list of team names to filter conflicts
- `--excel-file` - Path to Excel file containing existing tournament dates
- `--start-date` - Start date in YYYY-MM-DD format (default: today)
- `--end-date` - End date in YYYY-MM-DD format (default: 6 months from start)
- `--reschedule` - Reschedule tournament from this date in YYYY-MM-DD format (requires --excel-file)

### Rescheduling Mode

When using `--reschedule`, the system will:
1. Extract all teams participating in the tournament on the specified date from the Excel file
2. Search for alternative weekend dates in the specified range
3. Check that ALL teams are available on each candidate date
4. Apply all standard conflict checks (ice hall, ball hall, holidays, other tournaments)
5. Return only dates when all teams are free and no other conflicts exist

## Excel File Format

The Excel file can contain tournament dates in various formats:
- DateTime cells (preferred)
- Text dates in formats: DD.MM.YYYY, DD/MM/YYYY, YYYY-MM-DD

Example structure:
```
| Tournament Name      | Date       |
|---------------------|------------|
| Winter Cup 2025     | 18.01.2025 |
| Spring Tournament   | 15.02.2025 |
```

## Output

### Interactive Mode Output

Example output with all features:

```
============================================================
RESULTAT
============================================================

Søkte: 10 helgedatoer
Ledige: 7 datoer
Blokkert: 3 datoer med konflikter

Grunner for blokkerte datoer:
  • Excel Team Conflict: 2 datoer
  • Holiday: 1 datoer

============================================================
✓ LEDIGE DATOER (alle 6 lag ledige):
============================================================
  2026-03-01 (Søndag) - Foreslått: 11:00-13:30 ⚠️  HELGE-KONFLIKT
      → Jar 6 spiller Lør feb 28: Frisk Asker - Askerhallen
      → Skien spiller Lør feb 28: Frisk Asker - Askerhallen
  2026-03-07 (Lørdag) - Foreslått: 11:00-13:30
  2026-03-08 (Søndag) - Foreslått: 14:00-16:30
  2026-03-15 (Søndag) - Foreslått: 14:00-16:30 ⚠️  HELGE-KONFLIKT
      → Sandefjord spiller Lør mar 14: Ringerike - Schjongshallen

────────────────────────────────────────────────────────────
DETALJERT TIDSPUNKT-TILGJENGELIGHET:
────────────────────────────────────────────────────────────
  2026-03-08: 14:00-16:30, 15:00-17:30
```

**Output includes:**
- **Summary statistics** - Total searched, available, blocked dates
- **Exclusion breakdown** - Reasons for blocked dates
- **Available dates** with:
  - Norwegian day names (Lørdag, Søndag)
  - **Suggested time slot** - Earliest possible start time
  - **Weekend conflict warnings** (⚠️) - Teams playing same weekend
  - Team-specific details showing venue and date
- **Detailed time slots** - All available time windows for each date

### Command-Line Mode Output

Traditional output format:
- List of available weekend dates in chronological order
- Summary statistics (total weekends checked, available, excluded)
- Breakdown of exclusion reasons:
  - Ice hall conflicts (other hockey tournaments)
  - Ball hall events (wardrobe unavailable)
  - Team schedule conflicts
  - Norwegian public holiday weeks
  - Excel-provided exclusions

## Search History

The interactive mode automatically saves all searches to `~/.hockey_scheduler_history.json`.

**Features:**
- Stores last 50 searches
- Browse and rerun previous searches
- Shows search summary with key parameters
- Includes timestamp for each search

**History format:**
```json
{
  "is_reschedule": true,
  "start_date": "2026-03-01",
  "end_date": "2026-03-15",
  "excel_file": "/path/to/schedule.xlsx",
  "tournament_date": "2026-01-31",
  "check_kongsberg_ice": false,
  "check_kongsberg_ball": false,
  "check_skien_ice": true,
  "timestamp": "2025-12-06T11:32:16"
}
```

To clear history:
```bash
rm ~/.hockey_scheduler_history.json
```

## Requirements

- Python 3.7+
- requests
- beautifulsoup4
- openpyxl
- holidays
- playwright (with chromium browser installed)
- icalendar
- recurring-ical-events

## Notes

- **Interactive mode** uses Norwegian language for all prompts and output
- **Weekend-only** - Only suggests Saturday and Sunday dates
- **Holiday exclusion** - Automatically excludes weekends before Norwegian public holidays
- **Multiple calendars**:
  - Kongsberg ice hall: Playwright-based Outlook calendar scraper
  - Kongsberg ball hall: Playwright-based Outlook calendar scraper
  - Skien ice hall: Google Calendar iCal feed (no browser required)
- **Time slot analysis** - Requires 2.5 hours minimum, suggests 11:00-14:00 window
- **Weekend warnings** - Same-weekend conflicts don't block dates, just warn
- If calendar scraping fails, the script continues with available data sources
