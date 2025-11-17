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


def scrape_calendar_with_playwright(url: str, calendar_type: str, start_date: datetime, end_date: datetime) -> List[Dict]:
    """Scrape Outlook calendar using Playwright to handle JavaScript rendering."""
    events = []

    # Calculate how many months to scrape
    current_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start_month = start_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_month = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Calculate months to navigate forward from current month to start month
    months_to_start = ((start_month.year - current_month.year) * 12 +
                       (start_month.month - current_month.month))

    # Calculate total months to scrape from start to end
    months_to_scrape = ((end_month.year - start_month.year) * 12 +
                        (end_month.month - start_month.month)) + 1

    try:
        with sync_playwright() as p:
            print(f"  Launching browser for {calendar_type}...", flush=True)
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            print(f"  Loading {calendar_type} calendar page...", flush=True)
            page.goto(url, timeout=30000)

            # Wait for iframe to load
            print(f"  Waiting for calendar to render...", flush=True)
            page.wait_for_timeout(2000)

            iframe_element = page.query_selector('iframe')
            if not iframe_element:
                print(f"Warning: Could not find {calendar_type} iframe")
                browser.close()
                return events

            iframe = iframe_element.content_frame()
            if not iframe:
                print(f"Warning: Could not load {calendar_type} iframe content")
                browser.close()
                return events

            # Wait for calendar to load
            print(f"  Accessing calendar iframe...", flush=True)
            iframe.wait_for_timeout(3000)

            # Navigate to start month if needed
            if months_to_start > 0:
                print(f"  Navigating to start month ({start_month.strftime('%B %Y')})...", flush=True)
                for _ in range(months_to_start):
                    try:
                        next_button = iframe.query_selector('button[aria-label*="Go to next month"]')
                        if next_button:
                            next_button.click()
                            iframe.wait_for_timeout(1000)
                    except Exception as e:
                        print(f"  Warning: Could not navigate to start month: {e}", flush=True)
                        break
            elif months_to_start < 0:
                print(f"  Navigating to start month ({start_month.strftime('%B %Y')})...", flush=True)
                for _ in range(abs(months_to_start)):
                    try:
                        prev_button = iframe.query_selector('button[aria-label*="Go to previous month"]')
                        if prev_button:
                            prev_button.click()
                            iframe.wait_for_timeout(1000)
                    except Exception as e:
                        print(f"  Warning: Could not navigate to start month: {e}", flush=True)
                        break

            # Scrape from start month to end month
            print(f"  Scraping {months_to_scrape} months of events ({start_month.strftime('%b %Y')} to {end_month.strftime('%b %Y')})...", flush=True)
            for month_offset in range(months_to_scrape):
                # Wait for content to load
                iframe.wait_for_timeout(1000)
                if month_offset > 0:
                    print(f"    Month {month_offset + 1}/{months_to_scrape}...", flush=True)

                # Extract HTML content from calendar (includes aria-labels)
                page_content = iframe.content()

                # Parse events from this month
                month_events = parse_outlook_calendar_text(page_content)
                events.extend(month_events)

                # Click "next month" button to navigate forward
                if month_offset < months_to_scrape - 1:
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

        print(f"  ✓ Scraped {len(unique_events)} events from {calendar_type} calendar\n", flush=True)

    except Exception as e:
        print(f"  ✗ Failed to scrape {calendar_type} calendar: {e}\n", file=sys.stderr, flush=True)

    return unique_events


def parse_outlook_calendar_text(text: str) -> List[Dict]:
    """Parse event data from Outlook calendar text content using aria-labels."""
    events = []

    # Norwegian month names for parsing
    months_no = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12,
        'januar': 1, 'februar': 2, 'mars': 3, 'april': 4,
        'mai': 5, 'juni': 6, 'juli': 7, 'august': 8,
        'september': 9, 'oktober': 10, 'november': 11, 'desember': 12
    }

    # Parse aria-label attributes which contain: "Event Name, HH:MM to HH:MM, Weekday, Month DD, YYYY"
    aria_pattern = r'aria-label="([^"]+)"'
    matches = re.findall(aria_pattern, text)

    for aria_label in matches:
        # Skip if it's not an event (e.g., navigation elements)
        if 'Go to' in aria_label or 'Print' in aria_label or 'Month' in aria_label:
            continue

        # Parse format: "Event Name, HH:MM to HH:MM, Weekday, Month DD, YYYY"
        parts = [p.strip() for p in aria_label.split(',')]

        if len(parts) >= 4:
            event_name = parts[0]

            # Extract time information (HH:MM AM/PM to HH:MM AM/PM or HH:MM to HH:MM)
            time_part = parts[1] if len(parts) > 1 else ''
            start_time = None
            end_time = None
            duration_hours = 0

            # Try AM/PM format first
            time_match = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM)\s+to\s+(\d{1,2}):(\d{2})\s*(AM|PM)', time_part, re.IGNORECASE)
            if time_match:
                start_hour, start_min, start_period, end_hour, end_min, end_period = time_match.groups()
                start_hour, start_min, end_hour, end_min = map(int, [start_hour, start_min, end_hour, end_min])

                # Convert to 24-hour format
                if start_period.upper() == 'PM' and start_hour != 12:
                    start_hour += 12
                elif start_period.upper() == 'AM' and start_hour == 12:
                    start_hour = 0

                if end_period.upper() == 'PM' and end_hour != 12:
                    end_hour += 12
                elif end_period.upper() == 'AM' and end_hour == 12:
                    end_hour = 0

                start_time = start_hour + start_min / 60.0
                end_time = end_hour + end_min / 60.0

                # Handle events that cross midnight
                if end_time < start_time:
                    end_time += 24
                duration_hours = end_time - start_time
            else:
                # Try 24-hour format
                time_match = re.search(r'(\d{1,2}):(\d{2})\s+to\s+(\d{1,2}):(\d{2})', time_part)
                if time_match:
                    start_hour, start_min, end_hour, end_min = map(int, time_match.groups())
                    start_time = start_hour + start_min / 60.0
                    end_time = end_hour + end_min / 60.0
                    # Handle events that cross midnight
                    if end_time < start_time:
                        end_time += 24
                    duration_hours = end_time - start_time

            # Find date components in the remaining parts
            # Look for month name and year
            found_date = None
            for i, part in enumerate(parts):
                # Check for month names
                for month_name, month_num in months_no.items():
                    if month_name in part.lower():
                        # Extract day and year from surrounding parts
                        # Expected format: "Month DD" and "YYYY" in different parts
                        day_match = re.search(r'\b(\d{1,2})\b', part)
                        year_match = None

                        # Look for year in current part or next parts
                        for j in range(i, min(i+2, len(parts))):
                            year_match = re.search(r'\b(20\d{2})\b', parts[j])
                            if year_match:
                                break

                        if day_match and year_match:
                            try:
                                found_date = datetime(
                                    int(year_match.group(1)),
                                    month_num,
                                    int(day_match.group(1))
                                )
                                break
                            except ValueError:
                                continue

                if found_date:
                    break

            if found_date and event_name:
                events.append({
                    'date': found_date.strftime('%d.%m.%Y'),
                    'name': event_name,
                    'datetime': found_date,
                    'duration_hours': duration_hours
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


def scrape_ice_hall_calendar(start_date: datetime, end_date: datetime) -> List[Dict]:
    """Scrape ice hall calendar to extract hockey tournament events."""
    url = "https://kongsberghallen.no/webkalender/ishall/"
    return scrape_calendar_with_playwright(url, "ice hall", start_date, end_date)


def scrape_ball_hall_calendar(start_date: datetime, end_date: datetime) -> List[Dict]:
    """Scrape ball hall calendar to identify wardrobe unavailability."""
    url = "https://kongsberghallen.no/webkalender/ballhall-dagtid-og-helg/"
    return scrape_calendar_with_playwright(url, "ball hall", start_date, end_date)


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

        print(f"  ✓ Parsed {len(dates)} dates from Excel file\n", flush=True)

    except FileNotFoundError:
        print(f"  ✗ Excel file not found: {file_path}\n", file=sys.stderr, flush=True)
        sys.exit(1)
    except Exception as e:
        print(f"  ✗ Failed to parse Excel file: {e}\n", file=sys.stderr, flush=True)
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


def is_tournament_event(event_name: str) -> bool:
    """Check if an event name indicates a tournament or major event."""
    event_name_lower = event_name.lower()

    # Tournament/competition keywords (Norwegian and English)
    tournament_keywords = [
        'turnering', 'tournament', 'cup', 'mesterskap', 'championship',
        'series', 'serie', 'finale', 'final', 'semifinale', 'playoff',
        'kvalifisering', 'qualifying', 'region', 'nm ', 'nasjonalt',
        'national', 'landsdel', 'krets'
    ]

    # Events that are NOT tournaments (exclude these)
    non_tournament_keywords = [
        'trening', 'practice', 'åpen ishall', 'open ice', 'reklag',
        'rek.lag', 'hockeytrim', 'pensjonist', 'helgevakt', 'duty',
        'is vedlikehold', 'maintenance', 'stengt', 'closed'
    ]

    # First check if it's explicitly NOT a tournament
    for keyword in non_tournament_keywords:
        if keyword in event_name_lower:
            return False

    # Then check if it contains tournament keywords
    for keyword in tournament_keywords:
        if keyword in event_name_lower:
            return True

    # If no keywords match, default to False (don't block the date)
    return False


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

    # Extract tournament dates from ice hall (not all events, only tournaments)
    ice_hall_dates = set()
    ice_hall_tournaments = []
    for event in ice_hall_events:
        event_name = event.get('name', '')
        # Only consider actual tournaments as conflicts
        if is_tournament_event(event_name):
            date_str = event.get('date')
            if date_str:
                for date_format in ['%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d']:
                    try:
                        date = datetime.strptime(date_str, date_format)
                        ice_hall_dates.add(date.date())
                        ice_hall_tournaments.append((date.date(), event_name))
                        break
                    except ValueError:
                        continue

    # Print found tournaments for debugging
    if ice_hall_tournaments:
        print(f"\nFound {len(set([d for d, _ in ice_hall_tournaments]))} tournament dates in ice hall:", flush=True)
        # Group by date and show unique dates
        tournament_by_date = {}
        for date, name in ice_hall_tournaments:
            if date not in tournament_by_date:
                tournament_by_date[date] = []
            tournament_by_date[date].append(name)

        for date in sorted(tournament_by_date.keys())[:10]:  # Show first 10
            names = ', '.join(set(tournament_by_date[date]))
            print(f"  {date.strftime('%Y-%m-%d')}: {names[:80]}", flush=True)
        if len(tournament_by_date) > 10:
            print(f"  ... and {len(tournament_by_date) - 10} more dates", flush=True)
    else:
        print("\nNo tournaments found in ice hall calendar", flush=True)

    # Extract ball hall dates (only events longer than 2 hours)
    ball_hall_dates = set()
    ball_hall_long_events = []
    for event in ball_hall_events:
        duration = event.get('duration_hours', 0)
        # Only count events longer than 2 hours as conflicts
        if duration > 2.0:
            date_str = event.get('date')
            if date_str:
                for date_format in ['%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d']:
                    try:
                        date = datetime.strptime(date_str, date_format)
                        ball_hall_dates.add(date.date())
                        ball_hall_long_events.append((date.date(), event.get('name', ''), duration))
                        break
                    except ValueError:
                        continue

    # Print found long ball hall events for debugging
    if ball_hall_long_events:
        print(f"Found {len(set([d for d, _, _ in ball_hall_long_events]))} ball hall events >2 hours:", flush=True)
        # Group by date
        events_by_date = {}
        for date, name, dur in ball_hall_long_events:
            if date not in events_by_date:
                events_by_date[date] = []
            events_by_date[date].append((name, dur))

        for date in sorted(events_by_date.keys())[:10]:  # Show first 10
            for name, dur in events_by_date[date]:
                print(f"  {date.strftime('%Y-%m-%d')}: {name[:50]} ({dur:.1f}h)", flush=True)
        if len(events_by_date) > 10:
            print(f"  ... and {len(events_by_date) - 10} more dates", flush=True)
    else:
        print("No ball hall events >2 hours found", flush=True)

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
    excluded_details = []

    for weekend_date in weekends:
        excluded = False
        reason = None

        if weekend_date in ice_hall_dates:
            exclusion_reasons['ice_hall'] += 1
            excluded = True
            # Find tournament name
            for date, name in ice_hall_tournaments:
                if date == weekend_date:
                    reason = f"Ice hall tournament: {name[:60]}"
                    break
            if not reason:
                reason = "Ice hall tournament"
        elif weekend_date in ball_hall_dates:
            exclusion_reasons['ball_hall'] += 1
            excluded = True
            # Find ball hall event details
            for date, name, dur in ball_hall_long_events:
                if date == weekend_date:
                    reason = f"Ball hall: {name[:40]} ({dur:.1f}h)"
                    break
            if not reason:
                reason = "Ball hall event"
        elif weekend_date in team_conflicts:
            exclusion_reasons['team_conflict'] += 1
            excluded = True
            # Find which team and event
            for event in ice_hall_events:
                event_date_str = event.get('date')
                if event_date_str:
                    try:
                        for date_format in ['%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d']:
                            try:
                                event_date = datetime.strptime(event_date_str, date_format).date()
                                if event_date == weekend_date:
                                    event_name = event.get('name', '').lower()
                                    for team in team_names:
                                        if team.lower() in event_name:
                                            reason = f"Team conflict: {event.get('name', '')[:50]}"
                                            break
                                    if reason:
                                        break
                                break
                            except ValueError:
                                continue
                    except:
                        continue
                if reason:
                    break
            if not reason:
                reason = "Team schedule conflict"
        elif weekend_date in holiday_weeks:
            exclusion_reasons['holiday_week'] += 1
            excluded = True
            # Find which holiday
            no_holidays = holidays.Norway()
            current = weekend_date - timedelta(days=weekend_date.weekday())
            for i in range(7):
                check_date = current + timedelta(days=i)
                if check_date in no_holidays:
                    holiday_name = no_holidays.get(check_date)
                    reason = f"Holiday week: {holiday_name}"
                    break
            if not reason:
                reason = "Holiday week"
        elif weekend_date in excel_dates:
            exclusion_reasons['excel'] += 1
            excluded = True
            reason = "Excel exclusion list"

        if excluded:
            excluded_details.append((weekend_date, reason))
        else:
            available.append(weekend_date)

    return available, exclusion_reasons, excluded_details


def format_output(available_dates: List[datetime], exclusion_reasons: Dict, total_weekends: int, excluded_details: List[Tuple] = None):
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
    print(f"  Ice hall tournaments: {exclusion_reasons['ice_hall']}")
    print(f"  Ball hall (wardrobe unavailable): {exclusion_reasons['ball_hall']}")
    print(f"  Team schedule conflicts: {exclusion_reasons['team_conflict']}")
    print(f"  Holiday weeks: {exclusion_reasons['holiday_week']}")
    print(f"  Excel-provided exclusions: {exclusion_reasons['excel']}")

    if excluded_details and len(excluded_details) <= 30:
        print("\n" + "-"*60)
        print("EXCLUDED WEEKENDS DETAIL")
        print("-"*60)
        for date, reason in sorted(excluded_details):
            print(f"  {date.strftime('%Y-%m-%d')} ({date.strftime('%a')}): {reason}")

    print("="*60 + "\n")
    print("Note: Only tournaments/competitions count as ice hall conflicts.")
    print("Regular practices, open hours, and maintenance are ignored.")
    print("Ball hall events only count as conflicts if they exceed 2 hours.\n")


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
    print("=" * 60)
    print("TOURNAMENT SCHEDULER")
    print("=" * 60)
    print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    if team_names:
        print(f"Filtering conflicts for teams: {', '.join(team_names)}")
    print("\nScraping calendars (this may take 30-60 seconds)...\n")

    ice_hall_events = scrape_ice_hall_calendar(start_date, end_date)
    ball_hall_events = scrape_ball_hall_calendar(start_date, end_date)

    # Parse Excel if provided
    excel_dates = set()
    if args.excel_file:
        print(f"Reading Excel file: {args.excel_file}")
        excel_dates = parse_excel_schedule(args.excel_file)

    # Find available weekends
    print("Analyzing conflicts and finding available dates...", flush=True)
    available_dates, exclusion_reasons, excluded_details = find_available_weekends(
        start_date, end_date,
        ice_hall_events, ball_hall_events,
        excel_dates, team_names
    )
    print("✓ Analysis complete\n", flush=True)

    # Calculate total weekends
    total_weekends = sum(1 for d in range((end_date - start_date).days + 1)
                        if (start_date + timedelta(days=d)).weekday() in [5, 6])

    # Output results
    format_output(available_dates, exclusion_reasons, total_weekends, excluded_details)


if __name__ == '__main__':
    main()
