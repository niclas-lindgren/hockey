#!/usr/bin/env python3
"""Interactive CLI for tournament scheduling."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

from tournament_scheduler.conflict_checkers.ball_hall_checker import BallHallConflictChecker
from tournament_scheduler.conflict_checkers.excel_team_checker import ExcelTeamConflictChecker
from tournament_scheduler.conflict_checkers.holiday_checker import HolidayConflictChecker
from tournament_scheduler.conflict_checkers.team_availability_checker import TeamAvailabilityChecker
from tournament_scheduler.conflict_checkers.timeslot_checker import TimeSlotChecker
from tournament_scheduler.conflict_checkers.tournament_checker import TournamentConflictChecker
from tournament_scheduler.data_sources.ball_hall_calendar import BallHallCalendar
from tournament_scheduler.data_sources.calendar_scraper import OutlookCalendarScraper
from tournament_scheduler.data_sources.ical_scraper import ICalScraper
from tournament_scheduler.data_sources.ice_hall_calendar import IceHallCalendar
from tournament_scheduler.excel.tournament_reader import ExcelTournamentReader
from tournament_scheduler.scheduler import TournamentScheduler
from tournament_scheduler.utils.date_parser import DateParser
from tournament_scheduler.utils.search_history import SearchHistory


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60)


def ask_choice(question, options):
    """Ask user to select from options."""
    print(f"\n{question}")
    for key, desc in options:
        print(f"  {key}. {desc}")

    while True:
        choice = input("\nDitt valg: ").strip()
        if any(choice == key for key, _ in options):
            return choice
        print(f"Ugyldig valg. Vennligst velg: {', '.join(k for k, _ in options)}")


def ask_yes_no(question, default=None):
    """Ask yes/no question."""
    if default is True:
        prompt = f"{question} [J/n]: "
    elif default is False:
        prompt = f"{question} [j/N]: "
    else:
        prompt = f"{question} [j/n]: "

    while True:
        response = input(prompt).strip().lower()
        if not response and default is not None:
            return default
        if response in ['j', 'ja', 'y', 'yes']:
            return True
        if response in ['n', 'nei', 'no']:
            return False
        print("Vennligst svar 'j' eller 'n'")


def ask_text(question, default=None, required=True):
    """Ask for text input."""
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
        print("Dette feltet er påkrevd.")


def ask_date(question, default=None):
    """Ask for a date in YYYY-MM-DD format."""
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
        print("Ugyldig datoformat. Bruk YYYY-MM-DD (f.eks. 2026-01-31)")


def ask_multi_choice(question, options):
    """Ask user to select multiple options."""
    print(f"\n{question}")
    print("(Skriv inn tall separert med komma, eller trykk Enter for å velge alle)")
    for key, desc in options:
        print(f"  {key}. {desc}")

    all_keys = [key for key, _ in options]

    while True:
        choice = input("\nDine valg (f.eks. 1,2 eller Enter for alle): ").strip()
        if not choice:
            return all_keys

        choices = [c.strip() for c in choice.split(',')]
        if all(c in all_keys for c in choices):
            return choices
        print(f"Ugyldig valg. Vennligst velg fra: {', '.join(all_keys)}")


def show_history_menu(history_manager):
    """Show history menu and let user select a previous search."""
    history = history_manager.load_history()

    if not history:
        print("\nIngen søkehistorikk funnet.")
        input("\nTrykk Enter for å fortsette...")
        return None

    print("\n" + "=" * 60)
    print("SØKEHISTORIKK")
    print("=" * 60)

    display_count = min(len(history), 20)
    for i in range(display_count):
        summary = history_manager.format_search_summary(history[i])
        print(f"  {i + 1}. {summary}")

    print(f"\n  0. Avbryt (gå tilbake)")

    while True:
        choice = input(f"\nVelg søk (1-{display_count}, eller 0 for å avbryte): ").strip()
        if choice == '0':
            return None

        try:
            idx = int(choice) - 1
            if 0 <= idx < display_count:
                return history[idx]
        except ValueError:
            pass

        print(f"Ugyldig valg. Vennligst velg 1-{display_count} eller 0.")


def collect_search_params():
    """Collect search parameters from user."""
    # Ask mode
    mode = ask_choice(
        "Hva ønsker du å gjøre?",
        [
            ("1", "Omplassere en eksisterende turnering (finn alternative datoer)"),
            ("2", "Finn ledige datoer for en ny turnering")
        ]
    )

    is_reschedule = (mode == "1")

    # Date range
    print("\n" + "-" * 60)
    print("DATOPERIODE")
    print("-" * 60)

    if is_reschedule:
        print("\nDefiner søkeområdet for alternative datoer.")

    start_date = ask_date("Startdato", datetime.now())
    default_end = start_date + timedelta(days=180)
    end_date = ask_date("Sluttdato", default_end)

    # Reschedule mode: Get Excel file and tournament date
    excel_file = None
    tournament_date = None

    if is_reschedule:
        print("\n" + "-" * 60)
        print("TURNERING SOM SKAL OMPLASSERES")
        print("-" * 60)

        excel_file = ask_text("\nExcel-fil med turneringsplan")
        if not Path(excel_file).exists():
            print(f"Feil: Filen ble ikke funnet: {excel_file}")
            sys.exit(1)

        tournament_date = ask_date("Turneringsdato som skal omplasseres")

    # Calendar sources
    print("\n" + "-" * 60)
    print("KALENDERKILDER")
    print("-" * 60)

    calendar_choices = ask_multi_choice(
        "Hvilke kalendere skal jeg sjekke?",
        [
            ("1", "Kongsberg ishall (lokale turneringer)"),
            ("2", "Kongsberg ballhall (garderobe-konflikter - kun advarsel)"),
            ("3", "Skien ishall (eksterne lag-konflikter)")
        ]
    )

    check_kongsberg_ice = "1" in calendar_choices
    check_kongsberg_ball = "2" in calendar_choices
    check_skien_ice = "3" in calendar_choices

    return {
        'is_reschedule': is_reschedule,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'excel_file': excel_file,
        'tournament_date': tournament_date.strftime('%Y-%m-%d') if tournament_date else None,
        'check_kongsberg_ice': check_kongsberg_ice,
        'check_kongsberg_ball': check_kongsberg_ball,
        'check_skien_ice': check_skien_ice
    }


def run_search(search_params):
    """Run a tournament search with given parameters."""
    # Extract and convert parameters
    is_reschedule = search_params['is_reschedule']
    start_date = DateParser.parse(search_params['start_date'])
    end_date = DateParser.parse(search_params['end_date'])
    excel_file = search_params.get('excel_file')
    tournament_date_str = search_params.get('tournament_date')
    tournament_date = DateParser.parse(tournament_date_str) if tournament_date_str else None
    check_kongsberg_ice = search_params['check_kongsberg_ice']
    check_kongsberg_ball = search_params['check_kongsberg_ball']
    check_skien_ice = search_params['check_skien_ice']

    # Execution
    print("\n" + "=" * 60)
    print("PROSESSERER...")
    print("=" * 60)

    # Initialize components
    outlook_scraper = OutlookCalendarScraper()
    skien_scraper = ICalScraper('istiderskienhockey@gmail.com')
    calendar_sources = []
    all_events_for_teams = []

    # Kongsberg ice hall
    if check_kongsberg_ice:
        print("\nHenter Kongsberg ishall-hendelser...")
        kongsberg_ice = IceHallCalendar("https://kongsberghallen.no/webkalender/ishall/", outlook_scraper)
        calendar_sources.append(kongsberg_ice)

        ice_events = kongsberg_ice.fetch_events(start_date, end_date)
        all_events_for_teams.extend(ice_events)

    # Kongsberg ball hall
    if check_kongsberg_ball:
        print("\nHenter Kongsberg ballhall-hendelser...")
        kongsberg_ball = BallHallCalendar(
            "https://kongsberghallen.no/webkalender/ballhall-dagtid-og-helg/",
            outlook_scraper
        )
        calendar_sources.append(kongsberg_ball)

        ball_events = kongsberg_ball.fetch_events(start_date, end_date)
        all_events_for_teams.extend(ball_events)

    # Skien ice hall
    if check_skien_ice:
        print("\nHenter Skien ishall-hendelser...")
        skien_ice = IceHallCalendar("https://skienishockey.no/kalender-isbooking/", skien_scraper)
        calendar_sources.append(skien_ice)

        skien_events = skien_ice.fetch_events(start_date, end_date)
        all_events_for_teams.extend(skien_events)

    print(f"\n  Totalt antall hendelser hentet: {len(all_events_for_teams)}")

    # Initialize conflict checkers
    checkers = []

    # Always check holidays
    checkers.append(HolidayConflictChecker())

    # Tournament checker for Kongsberg ice hall
    if check_kongsberg_ice:
        kongsberg_ice = IceHallCalendar("https://kongsberghallen.no/webkalender/ishall/", outlook_scraper)
        checkers.append(TournamentConflictChecker(kongsberg_ice))

    # Ball hall checker
    if check_kongsberg_ball:
        kongsberg_ball = BallHallCalendar(
            "https://kongsberghallen.no/webkalender/ballhall-dagtid-og-helg/",
            outlook_scraper
        )
        checkers.append(BallHallConflictChecker(kongsberg_ball))

    # Team availability checker
    if is_reschedule:
        print("\nAnalyserer Excel-fil...")
        excel_reader = ExcelTournamentReader(excel_file, DateParser())
        tournament_info = excel_reader.get_tournament_info(tournament_date.date())

        # Team checker with all events from calendars
        checkers.append(TeamAvailabilityChecker(all_events_for_teams))

        # Excel team checker
        checkers.append(ExcelTeamConflictChecker(excel_file, tournament_info.teams, DateParser()))

        # Get all tournament dates to exclude
        all_tournament_dates = excel_reader.get_all_tournament_dates()
        excel_dates = all_tournament_dates - {tournament_date.date()}
    else:
        tournament_info = None
        excel_dates = set()

    # Add time slot checker
    if all_events_for_teams:
        checkers.append(TimeSlotChecker(
            all_events_for_teams,
            min_duration_hours=2.5,
            earliest_start="11:00",
            latest_start="14:00"
        ))

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

    # Find timeslot checker and excel team checker
    timeslot_checker = None
    excel_team_checker = None
    for checker in checkers:
        if isinstance(checker, TimeSlotChecker):
            timeslot_checker = checker
        if isinstance(checker, ExcelTeamConflictChecker):
            excel_team_checker = checker

    # Display results
    print("\n" + "=" * 60)
    print("RESULTAT")
    print("=" * 60)

    print(f"\nSøkte: {result.total_weekends_checked} helgedatoer")
    print(f"Ledige: {len(result.available_dates)} datoer")
    print(f"Blokkert: {len(result.excluded_dates)} datoer med konflikter")

    if result.exclusion_breakdown:
        print(f"\nGrunner for blokkerte datoer:")
        for checker_name, count in sorted(result.exclusion_breakdown.items()):
            if checker_name != 'ball_hall_warning' and count > 0:
                print(f"  • {checker_name.replace('_', ' ').title()}: {count} datoer")

    if result.available_dates:
        print(f"\n{'=' * 60}")
        if is_reschedule:
            print(f"✓ LEDIGE DATOER (alle {len(tournament_info.teams)} lag ledige):")
        else:
            print(f"✓ LEDIGE DATOER:")
        print(f"{'=' * 60}")

        # Show dates with suggested time slots and warnings
        day_names_no = {
            'Monday': 'Mandag', 'Tuesday': 'Tirsdag', 'Wednesday': 'Onsdag',
            'Thursday': 'Torsdag', 'Friday': 'Fredag', 'Saturday': 'Lørdag', 'Sunday': 'Søndag'
        }
        for d in sorted(result.available_dates):
            day_name_en = d.strftime('%A')
            day_name = day_names_no.get(day_name_en, day_name_en)

            display_str = f"  {d.strftime('%Y-%m-%d')} ({day_name})"

            # Add suggested time slot
            if timeslot_checker:
                suggested_slot = timeslot_checker.get_suggested_slot(d)
                if suggested_slot:
                    display_str += f" - Foreslått: {suggested_slot}"

            # Check for weekend warnings
            has_warning = False
            if excel_team_checker and d in excel_team_checker.weekend_warnings:
                has_warning = True
                display_str += " ⚠️  HELGE-KONFLIKT"

            print(display_str)

            # Show warning details
            if has_warning:
                warning_teams = excel_team_checker.weekend_warnings[d]
                day_map = {'Mon': 'Man', 'Tue': 'Tir', 'Wed': 'Ons', 'Thu': 'Tor',
                          'Fri': 'Fre', 'Sat': 'Lør', 'Sun': 'Søn'}
                month_map = {'Jan': 'jan', 'Feb': 'feb', 'Mar': 'mar', 'Apr': 'apr',
                            'May': 'mai', 'Jun': 'jun', 'Jul': 'jul', 'Aug': 'aug',
                            'Sep': 'sep', 'Oct': 'okt', 'Nov': 'nov', 'Dec': 'des'}
                for team, event, conflict_date in warning_teams:
                    eng_date = conflict_date.strftime('%a %b %d')
                    nor_date = eng_date
                    for eng, nor in day_map.items():
                        nor_date = nor_date.replace(eng, nor)
                    for eng, nor in month_map.items():
                        nor_date = nor_date.replace(eng, nor)
                    print(f"      → {team} spiller {nor_date}: {event[:45]}")

        # Show detailed time slots
        if timeslot_checker and len(result.available_dates) <= 15:
            print(f"\n{'─' * 60}")
            print("DETALJERT TIDSPUNKT-TILGJENGELIGHET:")
            print(f"{'─' * 60}")
            for d in sorted(result.available_dates):
                slots = timeslot_checker.available_slots.get(d, [])
                if len(slots) > 1:
                    slots_str = ", ".join([f"{s[0]}-{s[1]}" for s in slots])
                    print(f"  {d.strftime('%Y-%m-%d')}: {slots_str}")
    else:
        print(f"\n{'=' * 60}")
        print("✗ INGEN LEDIGE DATOER FUNNET")
        print(f"{'=' * 60}")
        print("  Alle datoer har konflikter. Prøv:")
        print("  • Utvid datoperioden")
        print("  • Sjekk færre kalendere")
        if is_reschedule:
            print("  • Sjekk om lag-planer kan justeres")

    print("\n" + "=" * 60 + "\n")


def main():
    """Main interactive CLI."""
    history_manager = SearchHistory()

    while True:
        print_header("HOCKEY TURNERING PLANLEGGER")
        print("Interaktiv modus - Jeg guider deg gjennom valgene")

        # Main menu
        mode = ask_choice(
            "\nHva ønsker du å gjøre?",
            [
                ("1", "Nytt søk"),
                ("2", "Velg fra søkehistorikk"),
                ("3", "Avslutt")
            ]
        )

        if mode == "3":
            print("\nAvslutter...")
            break

        search_params = None

        if mode == "1":
            # Collect new search parameters
            search_params = collect_search_params()
        elif mode == "2":
            # Show history menu
            search_params = show_history_menu(history_manager)
            if not search_params:
                continue  # User cancelled, back to main menu

        if search_params:
            # Run the search
            run_search(search_params)

            # Save to history
            history_manager.save_search(search_params)

            # Ask if user wants to do another search
            print()
            if not ask_yes_no("Vil du gjøre et nytt søk?", default=True):
                print("\nAvslutter...")
                break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nAvbrutt av bruker.")
        sys.exit(0)
    except Exception as e:
        print(f"\nFeil: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
