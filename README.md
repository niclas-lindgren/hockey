# Hockey Tournament Scheduler

Find optimal weekend dates for hockey tournaments by analyzing conflicts from multiple sources.

## Features

- Scrapes Kongsberg Hall ice hall calendar for hockey tournament conflicts
- Scrapes Kongsberg Hall ball hall calendar for wardrobe unavailability
- Filters dates based on specific team schedules
- Excludes Norwegian public holiday weeks
- Supports Excel files with existing tournament dates
- Weekend-only suggestions (Saturday and Sunday)

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

Using the shell script (recommended):
```bash
./tournament-scheduler.sh --start-date 2025-01-01 --end-date 2025-06-30
```

Or run directly with Python:
```bash
python tournament_scheduler.py --start-date 2025-01-01 --end-date 2025-06-30
```

Filter by team names:
```bash
./tournament-scheduler.sh --teams "Vikings,Bears,Eagles" --start-date 2025-01-01
```

Include Excel file with existing tournaments:
```bash
./tournament-scheduler.sh --excel-file existing_tournaments.xlsx --teams "Vikings"
```

Full example:
```bash
./tournament-scheduler.sh \
  --teams "Team A,Team B,Team C" \
  --excel-file tournaments.xlsx \
  --start-date 2025-01-01 \
  --end-date 2025-12-31
```

## Command-Line Options

- `--teams` - Comma-separated list of team names to filter conflicts
- `--excel-file` - Path to Excel file containing existing tournament dates
- `--start-date` - Start date in YYYY-MM-DD format (default: today)
- `--end-date` - End date in YYYY-MM-DD format (default: 6 months from start)

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
