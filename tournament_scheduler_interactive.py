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
from tournament_scheduler.utils.rich_output import TournamentOutput


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

        # Get ALL ice events for timeslot checking (includes open ice, practices, etc.)
        ice_events = outlook_scraper.scrape_calendar(
            "https://kongsberghallen.no/webkalender/ishall/",
            "Kongsberg ishall",
            start_date,
            end_date
        )
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

        # Get ALL Skien events for timeslot checking
        skien_events = skien_scraper.scrape_calendar(
            "https://skienishockey.no/kalender-isbooking/",
            "Skien ishall",
            start_date,
            end_date
        )
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
            latest_start="15:00"
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
    TournamentOutput.print_summary(
        result.total_weekends_checked,
        len(result.available_dates),
        len(result.excluded_dates),
        result.exclusion_breakdown or {}
    )

    if result.available_dates:
        # Prepare dates with slots for Rich display
        day_names_no = {
            'Monday': 'Mandag', 'Tuesday': 'Tirsdag', 'Wednesday': 'Onsdag',
            'Thursday': 'Torsdag', 'Friday': 'Fredag', 'Saturday': 'Lørdag', 'Sunday': 'Søndag'
        }

        dates_with_slots = []
        dates_with_all_slots = []

        for d in sorted(result.available_dates):
            day_name_en = d.strftime('%A')
            day_name = day_names_no.get(day_name_en, day_name_en)

            # Get suggested time slot
            time_slot = ""
            if timeslot_checker:
                time_slot = timeslot_checker.get_suggested_slot(d)

            # Check for weekend warnings
            has_warning = excel_team_checker and d in excel_team_checker.weekend_warnings

            dates_with_slots.append((d, day_name, time_slot, has_warning))

            # Get all slots for detailed view
            if timeslot_checker:
                all_slots = timeslot_checker.available_slots.get(d, [])
                if len(all_slots) > 1:
                    dates_with_all_slots.append((d, day_name, all_slots))

        TournamentOutput.print_available_dates(dates_with_slots)

        # Show detailed time slots if there are multiple options
        if dates_with_all_slots and len(result.available_dates) <= 15:
            TournamentOutput.print_time_slots_detail(dates_with_all_slots)

        # Show weekend warning details
        if excel_team_checker and excel_team_checker.weekend_warnings:
            from rich.console import Console
            console = Console()
            console.print("\n[yellow]Detaljer om helgekonflikter:[/yellow]")
            for d in sorted(result.available_dates):
                if d in excel_team_checker.weekend_warnings:
                    warning_teams = excel_team_checker.weekend_warnings[d]
                    for team, event, conflict_date in warning_teams:
                        console.print(
                            f"  {d.strftime('%Y-%m-%d')}: [cyan]{team}[/cyan] "
                            f"spiller {conflict_date.strftime('%Y-%m-%d')} - {event[:50]}"
                        )
    else:
        TournamentOutput.print_no_dates_found()


def collect_roster_entries():
    """Prompt the user for club/team roster entries (e.g. "Jar 1, Jar 2 - U10").

    Returns ``(Roster, federation_defaults)`` where ``federation_defaults`` is
    the dict under the ``federationDefaults`` key in an extended input file
    (contains ``parallelGames`` and ``maxTeamsPerTournament`` sub-dicts), or an
    empty dict when roster is entered manually or a flat file is used.
    """
    from tournament_scheduler.models import Team, Roster
    from tournament_scheduler.club_registry import CLUB_REGISTRY
    from tournament_scheduler.roster_loader import RosterConfigError, RosterLoader

    print("\n" + "-" * 60)
    print("LAGTROPP FOR SESONGEN")
    print("-" * 60)
    print("\nDu kan laste lagtroppen fra en fil (YAML/JSON), f.eks.:")
    print('  {"clubs": {"Jar": {"U10": ["Jar 1"]}}, "federationDefaults": {...}}')
    print("La stå tomt for å skrive inn lagene manuelt i stedet.\n")

    while True:
        roster_file = ask_text("Filsti til lagtroppskonfigurasjon", default="", required=False)
        if not roster_file:
            break

        try:
            roster, federation_defaults = RosterLoader.load_with_defaults(roster_file)
        except RosterConfigError as exc:
            print(f"  {exc}")
            retry = ask_text(
                "Prøv en annen fil? (j/n)", default="j", required=False
            )
            if retry.strip().lower().startswith("j"):
                continue
            print("  Går videre til manuell innlegging av lag.\n")
            break

        print(
            f"  Lastet inn {len(roster.teams)} lag fordelt på {len(roster.clubs())} klubber "
            f"og {len(roster.age_groups())} aldersgrupper."
        )
        if federation_defaults:
            print("  Forbundsstandarder lastet fra fil.")
        return roster, federation_defaults

    print("\nSkriv inn ett lag per linje på formatet: <Klubb> <Lagnavn> - <Aldersgruppe>")
    print("Eksempel: Jar 1 - U10")
    print("Skriv en tom linje når du er ferdig.\n")

    teams = []
    while True:
        line = input("Lag (tom linje for å avslutte): ").strip()
        if not line:
            break

        if " - " not in line:
            print("  Ugyldig format. Bruk: <Klubb> <Lagnavn> - <Aldersgruppe> (f.eks. 'Jar 1 - U10')")
            continue

        label_part, age_group = (part.strip() for part in line.rsplit(" - ", 1))
        if not label_part or not age_group:
            print("  Ugyldig format. Bruk: <Klubb> <Lagnavn> - <Aldersgruppe> (f.eks. 'Jar 1 - U10')")
            continue

        # The club name is the leading word(s) of the label, e.g. "Jar" from "Jar 1".
        club = label_part.rsplit(" ", 1)[0] if " " in label_part else label_part
        if club not in CLUB_REGISTRY:
            print(f"  Advarsel: '{club}' er ikke en kjent RVV-klubb. Lagt til likevel.")

        teams.append(Team(club=club, label=label_part, age_group=age_group))
        print(f"  Lagt til: {label_part} ({age_group})")

    if not teams:
        print("\nIngen lag lagt til.")
        return None, {}

    return Roster(teams=teams), {}


def collect_season_plan_params():
    """Collect parameters for generating a full season schedule."""
    from tournament_scheduler.models import Roster

    roster, federation_defaults = collect_roster_entries()
    if not roster:
        return None

    print("\n" + "-" * 60)
    print("SESONGVINDU")
    print("-" * 60)

    today = datetime.now()
    default_start = today.replace(month=10, day=1)
    if default_start < today:
        default_start = default_start.replace(year=default_start.year + 1)
    default_end = default_start.replace(year=default_start.year + 1, month=4, day=30)

    season_start = ask_date("Sesongstart", default_start)
    season_end = ask_date("Sesongslutt", default_end)

    return {
        'season_plan': True,
        'roster': roster,
        'season_start': season_start.strftime('%Y-%m-%d'),
        'season_end': season_end.strftime('%Y-%m-%d'),
        'federation_defaults': federation_defaults,
    }


def run_season_plan(params):
    """Generate, render, and optionally export a full-season tournament plan."""
    from tournament_scheduler.club_registry import known_clubs, missing_clubs, build_data_source
    from tournament_scheduler.season_planner import SeasonPlanner


    roster = params['roster']
    season_start = DateParser.parse(params['season_start'])
    season_end = DateParser.parse(params['season_end'])

    TournamentOutput.print_header("GENERERER SESONGPLAN")
    TournamentOutput.print_info(
        f"Sesongvindu: {season_start.strftime('%Y-%m-%d')} til {season_end.strftime('%Y-%m-%d')}"
    )
    TournamentOutput.print_success(
        f"Lagtropp: {len(roster.teams)} lag fordelt på {len(roster.clubs())} klubber "
        f"og {len(roster.age_groups())} aldersgrupper"
    )

    federation_defaults = params.get('federation_defaults') or {}
    parallel_games_for_age_group = federation_defaults.get('parallelGames', {})
    max_teams_per_tournament_for_age_group = federation_defaults.get('maxTeamsPerTournament', {})

    sources = []
    club_arenas = {}
    for entry in known_clubs():
        source = build_data_source(entry)
        if source is not None:
            sources.append(source)
            club_arenas[entry.club] = entry.arena

    for entry in missing_clubs():
        TournamentOutput.print_warning(
            f"Hopper over {entry.club} — kalenderkilde mangler ennå ({entry.note or 'ingen URL'})"
        )

    if not sources:
        TournamentOutput.print_error("Ingen klubber med kjente kalenderkilder funnet — kan ikke generere sesongplan.")
        return

    checkers = [HolidayConflictChecker()]
    for source in sources:
        try:
            checkers.append(TournamentConflictChecker(source))
        except Exception:
            pass

    scheduler = TournamentScheduler(
        calendar_sources=sources,
        conflict_checkers=checkers,
        date_parser=DateParser()
    )

    planner = SeasonPlanner(
        scheduler=scheduler,
        roster=roster,
        club_arenas=club_arenas,
        parallel_games_for_age_group=parallel_games_for_age_group,
        max_teams_per_tournament_for_age_group=max_teams_per_tournament_for_age_group,
    )

    TournamentOutput.print_info("Bygger sesongplan (dette kan ta litt tid)...")
    plan = planner.build_plan(season_start, season_end)

    if not plan.tournaments:
        TournamentOutput.print_no_dates_found()
        return

    TournamentOutput.print_season_overview(plan)
    for tournament in sorted(plan.tournaments, key=lambda t: t.date):
        TournamentOutput.print_tournament_schedule(tournament)
    TournamentOutput.print_diversity_summary(plan)

    if ask_yes_no("\nVil du eksportere sesongplanen til Excel?", default=True):
        export_path = ask_text("Filnavn for Excel-eksport", default="sesongplan.xlsx")
        from tournament_scheduler.excel.plan_exporter import SeasonPlanExporter
        SeasonPlanExporter().export(plan, export_path)


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
                ("3", "Generer full sesongplan"),
                ("4", "Avslutt")
            ]
        )

        if mode == "4":
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
        elif mode == "3":
            # Generate a full season schedule
            season_params = collect_season_plan_params()
            if season_params:
                run_season_plan(season_params)

                print()
                if not ask_yes_no("Vil du gjøre noe mer?", default=True):
                    print("\nAvslutter...")
                    break
            continue

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
