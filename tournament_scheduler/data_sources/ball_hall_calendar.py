"""Ball hall calendar data source."""

from datetime import datetime
from typing import List
from tournament_scheduler.interfaces import CalendarDataSource
from tournament_scheduler.models import CalendarEvent
from tournament_scheduler.data_sources.calendar_scraper import CalendarScraper


class BallHallCalendar(CalendarDataSource):
    """Ball hall calendar implementation - filters for long events."""

    def __init__(self, url: str, scraper: CalendarScraper, min_duration: float = 2.0):
        """Initialize ball hall calendar.

        Args:
            url: Calendar URL
            scraper: CalendarScraper instance
            min_duration: Minimum event duration in hours to consider as conflict
        """
        self.url = url
        self.scraper = scraper
        self.min_duration = min_duration

    def fetch_events(self, start_date: datetime, end_date: datetime) -> List[CalendarEvent]:
        """Fetch ball hall events, filtering for events exceeding minimum duration.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of long ball hall events
        """
        all_events = self.scraper.scrape_calendar(self.url, "ball hall", start_date, end_date)
        return [event for event in all_events if event.duration_hours > self.min_duration]

    def get_source_name(self) -> str:
        """Get source name.

        Returns:
            'ball_hall'
        """
        return 'ball_hall'
