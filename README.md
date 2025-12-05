# Hockey Tournament Scheduler

Find optimal weekend dates for hockey tournaments by analyzing conflicts from multiple sources.

## Features

- Scrapes Kongsberg Hall ice hall calendar for hockey tournament conflicts
- Scrapes Kongsberg Hall ball hall calendar for wardrobe unavailability
- Filters dates based on specific team schedules
- Excludes Norwegian public holiday weeks
- Supports Excel files with existing tournament dates
- Weekend-only suggestions (Saturday and Sunday)
- **NEW: Reschedule existing tournaments** - Find alternative dates when all teams are available

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

Show help and examples:
```bash
./tournament-scheduler.sh --help
```

Basic usage:
```bash
./tournament-scheduler.sh --start-date 2025-01-01 --end-date 2025-06-30
```

Filter by team names to exclude their scheduled dates:
```bash
./tournament-scheduler.sh --teams "Kongsberg,Drammen,Oslo" --start-date 2025-01-01 --end-date 2025-12-31
```

Include Excel file with existing tournaments:
```bash
./tournament-scheduler.sh --excel-file existing_tournaments.xlsx --start-date 2025-03-01
```

Full example with all options:
```bash
./tournament-scheduler.sh \
  --teams "Team A,Team B,Team C" \
  --excel-file tournaments.xlsx \
  --start-date 2025-01-01 \
  --end-date 2025-12-31
```

Reschedule an existing tournament:
```bash
./tournament-scheduler.sh \
  --reschedule 2026-01-17 \
  --excel-file existing_schedule/tournament_schedule.xlsx \
  --start-date 2026-02-01 \
  --end-date 2026-06-30
```

Or run directly with Python:
```bash
python tournament_scheduler.py --start-date 2025-01-01 --end-date 2025-06-30
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

The script outputs:
- List of available weekend dates in chronological order
- Summary statistics (total weekends checked, available, excluded)
- Breakdown of exclusion reasons:
  - Ice hall conflicts (other hockey tournaments)
  - Ball hall events (wardrobe unavailable)
  - Team schedule conflicts
  - Norwegian public holiday weeks
  - Excel-provided exclusions

## Requirements

- Python 3.7+
- requests
- beautifulsoup4
- openpyxl
- holidays
- playwright (with chromium browser installed)

## Notes

- The script only suggests weekend dates (Saturday and Sunday)
- Weeks containing Norwegian public holidays are automatically excluded
- The script uses Playwright to scrape JavaScript-rendered Outlook calendars
- Calendar scraping requires Playwright browsers to be installed (run: `playwright install chromium`)
- If calendar scraping fails, the script continues with available data sources
