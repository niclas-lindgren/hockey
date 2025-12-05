"""Tournament conflict checker for ice hall."""

from datetime import date
from typing import List
from tournament_scheduler.interfaces import ConflictChecker
from tournament_scheduler.models import ConflictContext, ConflictResult
from tournament_scheduler.data_sources.ice_hall_calendar import IceHallCalendar
from tournament_scheduler.utils.date_parser import DateParser


class TournamentConflictChecker(ConflictChecker):
    """Checks for conflicts with ice hall tournaments."""

    def __init__(self, calendar_source: IceHallCalendar):
        """Initialize tournament checker.

        Args:
            calendar_source: IceHallCalendar instance
        """
        self.calendar_source = calendar_source

    def check_conflicts(self, dates: List[date], context: ConflictContext) -> ConflictResult:
        """Check for tournament conflicts.

        Args:
            dates: Dates to check
            context: Context with calendar events

        Returns:
            ConflictResult with excluded dates
        """
        excluded_dates = set()
        reasons = {}

        # Build tournament dates from context events (already filtered for tournaments)
        tournament_dates = {}
        for event in context.calendar_events:
            # Only check events that are tournaments (ice hall events are already filtered)
            if self.calendar_source._is_tournament_event(event.name):
                parsed = DateParser.parse(event.date)
                if parsed:
                    event_date = parsed.date()
                    tournament_dates[event_date] = event.name

        # Check each date
        for check_date in dates:
            if check_date in tournament_dates:
                excluded_dates.add(check_date)
                reasons[check_date] = f"Ice hall tournament: {tournament_dates[check_date][:60]}"

        return ConflictResult(
            excluded_dates=excluded_dates,
            reasons=reasons,
            checker_name=self.get_checker_name()
        )

    def get_checker_name(self) -> str:
        """Get checker name.

        Returns:
            'ice_hall'
        """
        return 'ice_hall'
