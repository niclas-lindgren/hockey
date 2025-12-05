"""Abstract interfaces for tournament scheduling components."""

from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import List
from tournament_scheduler.models import CalendarEvent, ConflictContext, ConflictResult


class CalendarDataSource(ABC):
    """Abstract base class for calendar data sources."""

    @abstractmethod
    def fetch_events(self, start_date: datetime, end_date: datetime) -> List[CalendarEvent]:
        """Fetch calendar events for the specified date range.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of calendar events
        """
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """Get the name of this data source.

        Returns:
            Data source name
        """
        pass


class ConflictChecker(ABC):
    """Abstract base class for conflict checkers."""

    @abstractmethod
    def check_conflicts(self, dates: List[date], context: ConflictContext) -> ConflictResult:
        """Check for conflicts on the specified dates.

        Args:
            dates: List of dates to check
            context: Context containing all data needed for checking

        Returns:
            ConflictResult with excluded dates and reasons
        """
        pass

    @abstractmethod
    def get_checker_name(self) -> str:
        """Get the name of this conflict checker.

        Returns:
            Checker name
        """
        pass
