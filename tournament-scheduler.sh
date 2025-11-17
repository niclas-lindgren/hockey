#!/bin/bash
# Tournament Scheduler Runner
# Activates virtual environment and runs the tournament scheduler

show_help() {
    cat << EOF
Tournament Scheduler - Find available weekend dates for hockey tournaments

Usage: $0 [OPTIONS]

Options:
  --start-date DATE       Start date (YYYY-MM-DD), default: today
  --end-date DATE         End date (YYYY-MM-DD), default: 6 months from start
  --teams TEAMS           Comma-separated team names to exclude conflicts
  --excel-file FILE       Excel file with existing tournament dates to exclude

Examples:
  # Find available dates for next 6 months
  $0 --start-date 2025-01-01 --end-date 2025-06-30

  # Exclude dates when specific teams are playing
  $0 --teams "U8,U9,U10" --start-date 2026-01-01 --end-date 2026-12-31

  # Use Excel file with existing tournaments
  $0 --excel-file tournaments.xlsx --start-date 2025-03-01

  # Full example with all options
  $0 --teams "U9,U10,U14" --excel-file /Users/niclas/private/hockey/existing_schedule/U10_ETTER_JUL_Klar_-_Kongsberg_Sandefjord.xlsx --start-date 2026-01-01 --end-date 2026-02-28

EOF
    exit 0
}

# Check for help flag
if [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
    show_help
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found. Run: python3 -m venv venv && venv/bin/pip install -r requirements.txt"
    exit 1
fi

source venv/bin/activate
python tournament_scheduler.py "$@"
