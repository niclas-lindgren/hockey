"""Default CLI mode: find available weekend dates for a new tournament."""

from datetime import datetime

from tournament_scheduler.club_registry import get_club
from tournament_scheduler.conflict_checkers.ball_hall_checker import BallHallConflictChecker
from tournament_scheduler.conflict_checkers.excel_checker import ExcelConflictChecker
from tournament_scheduler.conflict_checkers.holiday_checker import HolidayConflictChecker
from tournament_scheduler.conflict_checkers.team_availability_checker import TeamAvailabilityChecker
from tournament_scheduler.conflict_checkers.tournament_checker import TournamentConflictChecker
from tournament_scheduler.data_sources.ball_hall_calendar import BallHallCalendar
from tournament_scheduler.data_sources.calendar_scraper import CalendarScraper
from tournament_scheduler.data_sources.calendar_source_factory import build_calendar_source
from tournament_scheduler.excel.tournament_reader import ExcelTournamentReader
from tournament_scheduler.scheduler import TournamentScheduler
from tournament_scheduler.utils.date_parser import DateParser
from tournament_scheduler.utils.rich_output import TournamentOutput


class SchedulingCommand:
    """Finds available weekend dates for a new tournament (default mode)."""

    def run(self, args, start_date: datetime, end_date: datetime) -> None:
        team_names = [t.strip() for t in args.teams.split(',') if t.strip()]

        TournamentOutput.print_header("TOURNAMENT SCHEDULER")
        TournamentOutput.print_info(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        if team_names:
            TournamentOutput.print_info(f"Filtering conflicts for teams: {', '.join(team_names)}")
        TournamentOutput.print_info("Scraping calendars (this may take 30-60 seconds)...")

        scraper = CalendarScraper()
        kongsberg = get_club("Kongsberg")
        ice_hall_url = kongsberg.source
        ice_hall = build_calendar_source(kongsberg)
        ball_hall = BallHallCalendar("https://kongsberghallen.no/webkalender/ballhall-dagtid-og-helg/", scraper)

        all_ice_hall_events = scraper.scrape_calendar(ice_hall_url, "ice hall", start_date, end_date)
        ball_hall_events = ball_hall.fetch_events(start_date, end_date)
        all_events = all_ice_hall_events + ball_hall_events

        excel_dates = set()
        if args.excel_file:
            TournamentOutput.print_info(f"Reading Excel file: {args.excel_file}")
            excel_dates = ExcelTournamentReader(args.excel_file, DateParser()).get_all_tournament_dates()

        checkers = [
            HolidayConflictChecker(),
            TournamentConflictChecker(ice_hall),
            BallHallConflictChecker(ball_hall),
            ExcelConflictChecker(set()),  # excel_dates passed via find_available_dates below
        ]
        if team_names:
            checkers.append(TeamAvailabilityChecker(all_events))

        scheduler = TournamentScheduler(
            calendar_sources=[ice_hall, ball_hall],
            conflict_checkers=checkers,
            date_parser=DateParser()
        )

        TournamentOutput.print_info("Analyzing conflicts and finding available dates...")
        result = scheduler.find_available_dates(
            start_date=start_date,
            end_date=end_date,
            team_names=team_names,
            excel_dates=excel_dates,
            calendar_events=all_events
        )
        TournamentOutput.print_success("Analysis complete")

        self._print_results(result)

    def _print_results(self, result) -> None:
        TournamentOutput.print_summary(
            total_checked=result.total_weekends_checked,
            available_count=len(result.available_dates),
            blocked_count=len(result.excluded_dates),
            breakdown=result.exclusion_breakdown,
        )

        if result.available_dates:
            print(f"\n{'='*60}")
            print(f"✓ AVAILABLE DATES:")
            print(f"{'='*60}")
            for d in sorted(result.available_dates):
                day_name = d.strftime('%A')
                print(f"  {d.strftime('%Y-%m-%d')} ({day_name})")
            print()
        else:
            TournamentOutput.print_no_dates_found()
