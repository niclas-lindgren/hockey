"""Ice hall calendar data source."""

from datetime import datetime
from typing import List
from tournament_scheduler.interfaces import CalendarDataSource
from tournament_scheduler.models import CalendarEvent
from tournament_scheduler.data_sources.calendar_scraper import CalendarScraper


class IceHallCalendar(CalendarDataSource):
    """Ice hall calendar implementation - filters for tournaments only."""

    def __init__(self, url: str, scraper: CalendarScraper):
        """Initialize ice hall calendar.

        Args:
            url: Calendar URL
            scraper: CalendarScraper instance
        """
        self.url = url
        self.scraper = scraper
        self.tournament_keywords = [
            'turnering', 'tournament', 'cup', 'mesterskap', 'championship',
            'series', 'serie', 'finale', 'final', 'semifinale', 'playoff',
            'kvalifisering', 'qualifying', 'region', 'nm ', 'nasjonalt',
            'national', 'landsdel', 'krets', 'kamp'
        ]
        self.non_tournament_keywords = [
            'trening', 'practice', 'åpen ishall', 'open ice', 'reklag',
            'rek.lag', 'hockeytrim', 'pensjonist', 'helgevakt', 'duty',
            'is vedlikehold', 'maintenance', 'stengt', 'closed',
            'ef søndag', 'ef lørdag', 'ef mandag', 'ef tirsdag', 'ef onsdag',
            'ef torsdag', 'ef fredag'
        ]

    def fetch_events(self, start_date: datetime, end_date: datetime) -> List[CalendarEvent]:
        """Fetch ice hall events, filtering for tournaments only.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of tournament events
        """
        all_events = self.scraper.scrape_calendar(self.url, "ice hall", start_date, end_date)
        return [event for event in all_events if self._is_tournament_event(event.name)]

    def get_source_name(self) -> str:
        """Get source name.

        Returns:
            'ice_hall'
        """
        return 'ice_hall'

    def _is_tournament_event(self, event_name: str) -> bool:
        """Check if event is a tournament.

        Args:
            event_name: Name of the event

        Returns:
            True if tournament, False otherwise
        """
        event_name_lower = event_name.lower()

        # Check if explicitly NOT a tournament
        for keyword in self.non_tournament_keywords:
            if keyword in event_name_lower:
                return False

        # Check if contains tournament keywords
        for keyword in self.tournament_keywords:
            if keyword in event_name_lower:
                return True

        return False
