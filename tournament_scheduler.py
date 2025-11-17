#!/usr/bin/env python3
"""
Hockey Tournament Scheduler
Finds optimal weekend dates for hockey tournaments by analyzing conflicts from multiple sources.
"""

import argparse
import sys
import re
from datetime import datetime, timedelta
from typing import List, Dict, Set, Optional, Tuple
import openpyxl
import holidays
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


def scrape_calendar_with_playwright(url: str, calendar_type: str, months_ahead: int = 3) -> List[Dict]:
    """Scrape Outlook calendar using Playwright to handle JavaScript rendering."""
    events = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            print(f"Loading {calendar_type} calendar...")
            page.goto(url, timeout=30000)

            # Wait for iframe to load
            page.wait_for_timeout(2000)

            iframe_element = page.query_selector('iframe.responsive-iframe')
            if not iframe_element:
                print(f"Warning: Could not access {calendar_type} iframe")
                browser.close()
                return events

            iframe = iframe_element.content_frame()
            if not iframe:
                print(f"Warning: Could not load {calendar_type} iframe content")
                browser.close()
                return events

            # Wait for calendar to load
            iframe.wait_for_timeout(3000)

            # Scrape current month and next few months
            for month_offset in range(months_ahead):
                # Wait for content to load
                iframe.wait_for_timeout(1000)

                # Extract visible text from calendar
                page_content = iframe.inner_text('body')

                # Parse events from this month
                month_events = parse_outlook_calendar_text(page_content)
                events.extend(month_events)

                # Click "next month" button to navigate forward
                if month_offset < months_ahead - 1:
                    try:
                        # Find the "Go to next month" button
                        next_button = iframe.query_selector('button[aria-label*="Go to next month"]')

                        if next_button:
                            next_button.click()
                            iframe.wait_for_timeout(1500)  # Wait for calendar to update
                        else:
                            print(f"Could not find next month button in {calendar_type}")
                            break

                    except Exception as e:
                        print(f"Warning: Could not navigate months: {e}")
                        break

            browser.close()

        # Deduplicate events across months
        unique_events = []
        seen = set()
        for event in events:
            key = (event['date'], event['name'])
            if key not in seen:
                seen.add(key)
                unique_events.append(event)

        print(f"Scraped {len(unique_events)} events from {calendar_type} calendar")

    except Exception as e:
        print(f"Warning: Failed to scrape {calendar_type} calendar: {e}", file=sys.stderr)

    return unique_events


def parse_outlook_calendar_text(text: str) -> List[Dict]:
    """Parse event data from Outlook calendar text content."""
    events = []
    lines = text.split('\n')

    # Common Norwegian date patterns
    date_patterns = [
        r'(\d{1,2})\.(\d{1,2})\.(\d{4})',  # DD.MM.YYYY
        r'(\d{1,2})/(\d{1,2})/(\d{4})',    # DD/MM/YYYY
        r'(\d{4})-(\d{1,2})-(\d{1,2})',    # YYYY-MM-DD
    ]

    # Norwegian month names
    months_no = {
        'januar': 1, 'februar': 2, 'mars': 3, 'april': 4,
        'mai': 5, 'juni': 6, 'juli': 7, 'august': 8,
        'september': 9, 'oktober': 10, 'november': 11, 'desember': 12
    }

    current_date = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Try to find date in line
        found_date = None

        # Check numeric date patterns
        for pattern in date_patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    if pattern.startswith(r'\d{4}'):  # YYYY-MM-DD
                        year, month, day = match.groups()
                    else:  # DD.MM.YYYY or DD/MM/YYYY
                        day, month, year = match.groups()
                    found_date = datetime(int(year), int(month), int(day))
                    break
                except ValueError:
                    continue

        # Check for Norwegian month names
        if not found_date:
            for month_name, month_num in months_no.items():
                if month_name in line.lower():
                    # Try to extract day and year
                    day_match = re.search(r'\b(\d{1,2})\s+' + month_name, line.lower())
                    year_match = re.search(r'\b(20\d{2})\b', line)
                    if day_match and year_match:
                        try:
                            found_date = datetime(int(year_match.group(1)), month_num, int(day_match.group(1)))
                            break
                        except ValueError:
                            continue

        if found_date:
            current_date = found_date

        # If we have a current date and this line looks like an event name
        if current_date and line and len(line) > 3:
            # Skip lines that are just dates or times
            if not re.match(r'^[\d\s\.:/-]+$', line):
                events.append({
                    'date': current_date.strftime('%d.%m.%Y'),
                    'name': line,
                    'datetime': current_date
                })

    # Deduplicate events
    unique_events = []
    seen = set()
    for event in events:
        key = (event['date'], event['name'])
        if key not in seen:
            seen.add(key)
            unique_events.append(event)

    return unique_events


def scrape_ice_hall_calendar() -> List[Dict]:
    """Scrape ice hall calendar to extract hockey tournament events."""
    url = "https://kongsberghallen.no/webkalender/ishall/"
    return scrape_calendar_with_playwright(url, "ice hall")


def scrape_ball_hall_calendar() -> List[Dict]:
    """Scrape ball hall calendar to identify wardrobe unavailability."""
    url = "https://kongsberghallen.no/webkalender/ballhall-dagtid-og-helg/"
    return scrape_calendar_with_playwright(url, "ball hall")


def parse_excel_schedule(file_path: str) -> Set[datetime]:
    """Parse Excel file containing existing tournament dates."""
    dates = set()

    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        ws = wb.active

        for row in ws.iter_rows(min_row=1, values_only=True):
            for cell in row:
                if isinstance(cell, datetime):
                    dates.add(cell.date())
                elif isinstance(cell, str):
                    # Try parsing string dates
                    for date_format in ['%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d']:
                        try:
                            date = datetime.strptime(cell.strip(), date_format)
                            dates.add(date.date())
                            break
                        except (ValueError, AttributeError):
                            continue

        print(f"Parsed {len(dates)} dates from Excel file")

    except FileNotFoundError:
        print(f"Error: Excel file not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: Failed to parse Excel file: {e}", file=sys.stderr)
        sys.exit(1)

    return dates


def get_norwegian_holidays(start_date: datetime, end_date: datetime) -> Set[datetime]:
    """Get Norwegian public holidays and their surrounding weeks."""
    no_holidays = holidays.Norway()
    holiday_weeks = set()

    current = start_date
    while current <= end_date:
        if current in no_holidays:
            # Add entire week containing the holiday
            week_start = current - timedelta(days=current.weekday())
            for i in range(7):
                week_day = week_start + timedelta(days=i)
                holiday_weeks.add(week_day.date())
        current += timedelta(days=1)

    return holiday_weeks


def filter_team_conflicts(events: List[Dict], team_names: List[str]) -> Set[datetime]:
    """Extract dates where specified teams have conflicts."""
    conflict_dates = set()

    for event in events:
        event_name = event.get('name', '').lower()
        for team in team_names:
            if team.lower() in event_name:
                # Parse date from event
                date_str = event.get('date')
                if date_str:
                    for date_format in ['%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d']:
                        try:
                            date = datetime.strptime(date_str, date_format)
                            conflict_dates.add(date.date())
                            break
                        except ValueError:
                            continue

    return conflict_dates


def find_available_weekends(
    start_date: datetime,
    end_date: datetime,
    ice_hall_events: List[Dict],
    ball_hall_events: List[Dict],
    excel_dates: Set[datetime],
    team_names: List[str]
) -> Tuple[List[datetime], Dict]:
    """Find available weekend dates excluding all conflicts."""

    # Get all exclusion dates
    holiday_weeks = get_norwegian_holidays(start_date, end_date)
    team_conflicts = filter_team_conflicts(ice_hall_events, team_names)

    # Extract all ice hall and ball hall dates
    ice_hall_dates = set()
    for event in ice_hall_events:
        date_str = event.get('date')
        if date_str:
            for date_format in ['%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d']:
                try:
                    date = datetime.strptime(date_str, date_format)
                    ice_hall_dates.add(date.date())
                    break
                except ValueError:
                    continue

    ball_hall_dates = set()
    for event in ball_hall_events:
        date_str = event.get('date')
        if date_str:
            for date_format in ['%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d']:
                try:
                    date = datetime.strptime(date_str, date_format)
                    ball_hall_dates.add(date.date())
                    break
                except ValueError:
                    continue

    # Generate all weekend dates in range
    weekends = []
    current = start_date
    while current <= end_date:
        if current.weekday() in [5, 6]:  # Saturday or Sunday
            weekends.append(current.date())
        current += timedelta(days=1)

    # Filter available weekends
    available = []
    exclusion_reasons = {
        'ice_hall': 0,
        'ball_hall': 0,
        'team_conflict': 0,
        'holiday_week': 0,
        'excel': 0
    }

    for weekend_date in weekends:
        excluded = False

        if weekend_date in ice_hall_dates:
            exclusion_reasons['ice_hall'] += 1
            excluded = True
        elif weekend_date in ball_hall_dates:
            exclusion_reasons['ball_hall'] += 1
            excluded = True
        elif weekend_date in team_conflicts:
            exclusion_reasons['team_conflict'] += 1
            excluded = True
        elif weekend_date in holiday_weeks:
            exclusion_reasons['holiday_week'] += 1
            excluded = True
        elif weekend_date in excel_dates:
            exclusion_reasons['excel'] += 1
            excluded = True

        if not excluded:
            available.append(weekend_date)

    return available, exclusion_reasons


def format_output(available_dates: List[datetime], exclusion_reasons: Dict, total_weekends: int):
    """Format and display available dates and statistics."""
    print("\n" + "="*60)
    print("AVAILABLE WEEKEND DATES FOR TOURNAMENT")
    print("="*60 + "\n")

    if available_dates:
        for date in sorted(available_dates):
            day_name = date.strftime('%A')
            print(f"  {date.strftime('%Y-%m-%d')} ({day_name})")
        print(f"\nTotal available dates: {len(available_dates)}")
    else:
        print("  No available dates found in the specified range.")

    print("\n" + "-"*60)
    print("EXCLUSION SUMMARY")
    print("-"*60)
    print(f"Total weekends checked: {total_weekends}")
    print(f"Available: {len(available_dates)}")
    print(f"Excluded: {total_weekends - len(available_dates)}")
    print(f"\nExclusion breakdown:")
    print(f"  Ice hall conflicts: {exclusion_reasons['ice_hall']}")
    print(f"  Ball hall (wardrobe unavailable): {exclusion_reasons['ball_hall']}")
    print(f"  Team schedule conflicts: {exclusion_reasons['team_conflict']}")
    print(f"  Holiday weeks: {exclusion_reasons['holiday_week']}")
    print(f"  Excel-provided exclusions: {exclusion_reasons['excel']}")
    print("="*60 + "\n")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Find optimal weekend dates for hockey tournaments',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s --teams "Team A,Team B" --start-date 2025-01-01 --end-date 2025-06-30
  %(prog)s --excel-file tournaments.xlsx --teams "Vikings,Bears"
        '''
    )

    parser.add_argument('--teams', type=str, default='',
                        help='Comma-separated list of team names to filter conflicts')
    parser.add_argument('--excel-file', type=str,
                        help='Path to Excel file with existing tournament dates')
    parser.add_argument('--start-date', type=str,
                        help='Start date (YYYY-MM-DD), default: today')
    parser.add_argument('--end-date', type=str,
                        help='End date (YYYY-MM-DD), default: 6 months from start')

    args = parser.parse_args()

    # Parse dates
    if args.start_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
    else:
        start_date = datetime.now()

    if args.end_date:
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
    else:
        end_date = start_date + timedelta(days=180)  # 6 months

    # Parse team names
    team_names = [t.strip() for t in args.teams.split(',') if t.strip()]

    # Scrape calendars
    print("Scraping calendars...")
    ice_hall_events = scrape_ice_hall_calendar()
    ball_hall_events = scrape_ball_hall_calendar()

    # Parse Excel if provided
    excel_dates = set()
    if args.excel_file:
        excel_dates = parse_excel_schedule(args.excel_file)

    # Find available weekends
    print("\nAnalyzing dates...")
    available_dates, exclusion_reasons = find_available_weekends(
        start_date, end_date,
        ice_hall_events, ball_hall_events,
        excel_dates, team_names
    )

    # Calculate total weekends
    total_weekends = sum(1 for d in range((end_date - start_date).days + 1)
                        if (start_date + timedelta(days=d)).weekday() in [5, 6])

    # Output results
    format_output(available_dates, exclusion_reasons, total_weekends)


if __name__ == '__main__':
    main()
