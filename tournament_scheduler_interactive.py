#!/usr/bin/env python3
"""Interactive CLI for tournament scheduling."""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from tournament_scheduler.scheduler import TournamentScheduler
from tournament_scheduler.data_sources.calendar_scraper import OutlookCalendarScraper
from tournament_scheduler.data_sources.google_calendar_scraper import GoogleCalendarScraper
from tournament_scheduler.data_sources.ice_hall_calendar import IceHallCalendar
from tournament_scheduler.data_sources.ball_hall_calendar import BallHallCalendar
from tournament_scheduler.conflict_checkers.holiday_checker import HolidayConflictChecker
from tournament_scheduler.conflict_checkers.tournament_checker import TournamentConflictChecker
from tournament_scheduler.conflict_checkers.ball_hall_checker import BallHallConflictChecker
from tournament_scheduler.conflict_checkers.team_availability_checker import TeamAvailabilityChecker
from tournament_scheduler.conflict_checkers.excel_checker import ExcelConflictChecker
from tournament_scheduler.excel.tournament_reader import ExcelTournamentReader
from tournament_scheduler.utils.date_parser import DateParser


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60)


def ask_choice(question, options):
    """Ask user to select from options.

    Args:
        question: Question to ask
        options: List of (key, description) tuples

    Returns:
        Selected key
    """
    print(f"\n{question}")
    for key, desc in options:
        print(f"  {key}. {desc}")

    while True:
        choice = input("\nYour choice: ").strip()
        if any(choice == key for key, _ in options):
            return choice
        print(f"Invalid choice. Please enter one of: {', '.join(k for k, _ in options)}")


def ask_yes_no(question, default=None):
    """Ask yes/no question.

    Args:
        question: Question to ask
        default: Default answer (True/False/None)

    Returns:
        Boolean response
    """
    if default is True:
        prompt = f"{question} [Y/n]: "
    elif default is False:
        prompt = f"{question} [y/N]: "
    else:
        prompt = f"{question} [y/n]: "

    while True:
        response = input(prompt).strip().lower()
        if not response and default is not None:
            return default
        if response in ['y', 'yes']:
            return True
        if response in ['n', 'no']:
            return False
        print("Please answer 'y' or 'n'")


def ask_text(question, default=None, required=True):
    """Ask for text input.

    Args:
        question: Question to ask
        default: Default value
        required: Whether input is required

    Returns:
        User input string
    """
    if default:
        prompt = f"{question} [{default}]: "
    else:
        prompt = f"{question}: "

    while True:
        response = input(prompt).strip()
        if not response and default:
            return default
        if response or not required:
            return response
        print("This field is required.")


def ask_date(question, default=None):
    """Ask for a date in YYYY-MM-DD format.

    Args:
        question: Question to ask
        default: Default datetime object

    Returns:
        datetime object
    """
    if default:
        default_str = default.strftime('%Y-%m-%d')
        prompt = f"{question} (YYYY-MM-DD) [{default_str}]: "
    else:
        prompt = f"{question} (YYYY-MM-DD): "

    while True:
        response = input(prompt).strip()
        if not response and default:
            return default

        parsed = DateParser.parse(response)
        if parsed:
            return parsed
        print("Invalid date format. Please use YYYY-MM-DD (e.g., 2026-01-31)")


def ask_multi_choice(question, options):
    """Ask user to select multiple options.

    Args:
        question: Question to ask
        options: List of (key, description) tuples

    Returns:
        List of selected keys
    """
    print(f"\n{question}")
    print("(Enter numbers separated by commas, or press Enter to select all)")
    for key, desc in options:
        print(f"  {key}. {desc}")

    all_keys = [key for key, _ in options]

    while True:
        choice = input("\nYour choices (e.g., 1,2 or Enter for all): ").strip()
        if not choice:
            return all_keys

        choices = [c.strip() for c in choice.split(',')]
        if all(c in all_keys for c in choices):
            return choices
        print(f"Invalid choice. Please enter numbers from: {', '.join(all_keys)}")


def main():
    """Main interactive CLI."""
    print_header("HOCKEY TOURNAMENT SCHEDULER")
    print("Interactive mode - I'll guide you through the options")

    # Ask mode
    mode = ask_choice(
        "What would you like to do?",
        [
            ("1", "Reschedule an existing tournament (find alternative dates)"),
            ("2", "Find available dates for a new tournament")
        ]
    )

    is_reschedule = (mode == "1")

    # Common: Date range
    print("\n" + "-" * 60)
    print("DATE RANGE")
    print("-" * 60)

    if is_reschedule:
        print("\nDefine the search range for alternative dates.")

    start_date = ask_date("Start date", datetime.now())
    default_end = start_date + timedelta(days=180)
    end_date = ask_date("End date", default_end)

    # Reschedule mode: Get Excel file and tournament date
    excel_file = None
    tournament_date = None

    if is_reschedule:
        print("\n" + "-" * 60)
        print("TOURNAMENT TO RESCHEDULE")
        print("-" * 60)

        excel_file = ask_text("\nExcel file path with tournament schedule")
        if not Path(excel_file).exists():
            print(f"Error: File not found: {excel_file}")
            sys.exit(1)

        tournament_date = ask_date("Tournament date to reschedule")

    # Calendar sources
    print("\n" + "-" * 60)
    print("CALENDAR SOURCES")
    print("-" * 60)

    calendar_choices = ask_multi_choice(
        "Which calendars should I check?",
        [
            ("1", "Kongsberg ice hall (local tournaments)"),
            ("2", "Kongsberg ball hall (wardrobe conflicts - warning only)"),
            ("3", "Skien ice hall (external team conflicts)")
        ]
    )

    check_kongsberg_ice = "1" in calendar_choices
    check_kongsberg_ball = "2" in calendar_choices
    check_skien_ice = "3" in calendar_choices

    # Execution
    print("\n" + "=" * 60)
    print("PROCESSING...")
    print("=" * 60)

    # Initialize components
    outlook_scraper = OutlookCalendarScraper()
    google_scraper = GoogleCalendarScraper()
    calendar_sources = []
    all_events_for_teams = []

    # Kongsberg ice hall (Outlook calendar)
    if check_kongsberg_ice:
        print("\nFetching Kongsberg ice hall events...")
        kongsberg_ice = IceHallCalendar("https://kongsberghallen.no/webkalender/ishall/", outlook_scraper)
        calendar_sources.append(kongsberg_ice)

        # Fetch ALL events (unfiltered) for team checking
        ice_events = outlook_scraper.scrape_calendar(
            "https://kongsberghallen.no/webkalender/ishall/",
            "Kongsberg ice hall",
            start_date,
            end_date
        )
        all_events_for_teams.extend(ice_events)

    # Kongsberg ball hall (Outlook calendar)
    if check_kongsberg_ball:
        print("\nFetching Kongsberg ball hall events...")
        kongsberg_ball = BallHallCalendar(
            "https://kongsberghallen.no/webkalender/ballhall-dagtid-og-helg/",
            outlook_scraper
        )
        calendar_sources.append(kongsberg_ball)

        ball_events = kongsberg_ball.fetch_events(start_date, end_date)
        all_events_for_teams.extend(ball_events)

    # Skien ice hall (Google Calendar)
    if check_skien_ice:
        print("\nFetching Skien ice hall events...")
        skien_ice = IceHallCalendar("https://skienishockey.no/kalender-isbooking/", google_scraper)
        calendar_sources.append(skien_ice)

        skien_events = google_scraper.scrape_calendar(
            "https://skienishockey.no/kalender-isbooking/",
            "Skien ice hall",
            start_date,
            end_date
        )
        all_events_for_teams.extend(skien_events)

    print(f"\n  Total events fetched: {len(all_events_for_teams)}")

    # Initialize conflict checkers
    checkers = []

    # Always check holidays
    checkers.append(HolidayConflictChecker())

    # Tournament checker for Kongsberg ice hall
    if check_kongsberg_ice:
        kongsberg_ice = IceHallCalendar("https://kongsberghallen.no/webkalender/ishall/", outlook_scraper)
        checkers.append(TournamentConflictChecker(kongsberg_ice))

    # Ball hall checker (warnings only)
    if check_kongsberg_ball:
        kongsberg_ball = BallHallCalendar(
            "https://kongsberghallen.no/webkalender/ballhall-dagtid-og-helg/",
            outlook_scraper
        )
        checkers.append(BallHallConflictChecker(kongsberg_ball))

    # Team availability checker
    if is_reschedule:
        print("\nAnalyzing Excel file...")
        excel_reader = ExcelTournamentReader(excel_file, DateParser())
        tournament_info = excel_reader.get_tournament_info(tournament_date.date())

        # Team checker with all events
        checkers.append(TeamAvailabilityChecker(all_events_for_teams))

        # Get all tournament dates to exclude
        all_tournament_dates = excel_reader.get_all_tournament_dates()
        excel_dates = all_tournament_dates - {tournament_date.date()}
    else:
        tournament_info = None
        excel_dates = set()

    # Initialize scheduler
    scheduler = TournamentScheduler(
        calendar_sources=calendar_sources,
        conflict_checkers=checkers,
        date_parser=DateParser()
    )

    # Find available dates
    if is_reschedule:
        result = scheduler.find_available_dates(
            start_date=start_date,
            end_date=end_date,
            team_names=tournament_info.teams,
            excel_dates=excel_dates,
            calendar_events=all_events_for_teams
        )
        result.tournament_info = tournament_info
    else:
        result = scheduler.find_available_dates(
            start_date=start_date,
            end_date=end_date,
            team_names=[],
            excel_dates=excel_dates,
            calendar_events=all_events_for_teams
        )

    # Display results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    print(f"\nSearched: {result.total_weekends_checked} weekend dates")
    print(f"Available: {len(result.available_dates)} dates")
    print(f"Blocked: {len(result.excluded_dates)} dates with conflicts")

    if result.exclusion_breakdown:
        print(f"\nReasons for blocked dates:")
        for checker_name, count in sorted(result.exclusion_breakdown.items()):
            if checker_name != 'ball_hall_warning' and count > 0:
                print(f"  • {checker_name.replace('_', ' ').title()}: {count} dates")

    if result.available_dates:
        print(f"\n{'=' * 60}")
        if is_reschedule:
            print(f"✓ AVAILABLE DATES (all {len(tournament_info.teams)} teams free):")
        else:
            print(f"✓ AVAILABLE DATES:")
        print(f"{'=' * 60}")
        for d in sorted(result.available_dates):
            day_name = d.strftime('%A')
            print(f"  {d.strftime('%Y-%m-%d')} ({day_name})")
    else:
        print(f"\n{'=' * 60}")
        print("✗ NO AVAILABLE DATES FOUND")
        print(f"{'=' * 60}")
        print("  All dates have conflicts. Try:")
        print("  • Expanding the date range")
        print("  • Checking fewer calendars")
        if is_reschedule:
            print("  • Checking if team schedules can be adjusted")

    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
