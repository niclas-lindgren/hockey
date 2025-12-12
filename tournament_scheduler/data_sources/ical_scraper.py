"""iCal-based calendar scraper for Google Calendar public feeds."""

import requests
from datetime import datetime, timedelta
from typing import List, Optional
from icalendar import Calendar as iCalendar
import recurring_ical_events
from tournament_scheduler.models import CalendarEvent
from tournament_scheduler.interfaces import CalendarScraper
from tournament_scheduler.utils.calendar_cache import CalendarCache
from rich.console import Console

console = Console()


class ICalScraper(CalendarScraper):
    """Scrapes Google Calendar using public iCal feeds."""

    def __init__(self, calendar_id: str, cache: Optional[CalendarCache] = None):
        """Initialize iCal scraper.

        Args:
            calendar_id: Google Calendar ID (email format)
            cache: Optional CalendarCache instance for caching scraped events
        """
        self.calendar_id = calendar_id
        self.cache = cache or CalendarCache()

    def scrape_calendar(
        self,
        url: str,
        calendar_name: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[CalendarEvent]:
        """Scrape calendar events from iCal feed.

        Args:
            url: Not used (kept for interface compatibility)
            calendar_name: Display name for this calendar
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of CalendarEvent objects
        """
        events = []

        # Check cache first (use iCal URL as the "url" parameter)
        ical_url = f'https://calendar.google.com/calendar/ical/{self.calendar_id}/public/basic.ics'
        cached_events = self.cache.get(ical_url, calendar_name, start_date, end_date)
        if cached_events is not None:
            console.print(f"  [green]✓[/green] Bruker cachet {calendar_name} kalenderdata ([cyan]{len(cached_events)}[/cyan] hendelser)")
            return cached_events

        try:
            # Build iCal URL

            console.print(f"  [dim]Henter {calendar_name} iCal feed...[/dim]")
            response = requests.get(ical_url, timeout=15)

            if response.status_code != 200:
                console.print(f"  [red]✗[/red] Kunne ikke hente iCal feed: HTTP {response.status_code}", style="red")
                return events

            # Parse iCal data
            cal = iCalendar.from_ical(response.content)

            # Get events in date range
            # Add buffer to ensure we catch all events
            extended_end = end_date + timedelta(days=1)
            ical_events = recurring_ical_events.of(cal).between(start_date, extended_end)

            console.print(f"  [dim]Fant {len(ical_events)} hendelser i datoperioden[/dim]")

            # Convert to CalendarEvent objects
            for event in ical_events:
                start = event.get('DTSTART').dt
                end_dt = event.get('DTEND').dt if event.get('DTEND') else None
                summary = str(event.get('SUMMARY', ''))

                # Handle both date and datetime objects
                if hasattr(start, 'hour'):
                    # Event has time
                    event_datetime = start
                    event_date_str = start.strftime('%d.%m.%Y')

                    # Calculate duration
                    if end_dt and hasattr(end_dt, 'hour'):
                        duration_hours = (end_dt - start).total_seconds() / 3600
                    else:
                        duration_hours = 0
                else:
                    # All-day event
                    event_datetime = datetime.combine(start, datetime.min.time())
                    event_date_str = start.strftime('%d.%m.%Y')
                    duration_hours = 0

                events.append(CalendarEvent(
                    date=event_date_str,
                    name=summary,
                    datetime=event_datetime,
                    duration_hours=duration_hours
                ))

            # Deduplicate
            unique_events = []
            seen = set()
            for event in events:
                key = (event.date, event.name, event.datetime.hour if hasattr(event.datetime, 'hour') else 0)
                if key not in seen:
                    seen.add(key)
                    unique_events.append(event)

            console.print(f"  [green]✓[/green] Skrapte [cyan]{len(unique_events)}[/cyan] hendelser fra {calendar_name}")

            # Cache the results
            self.cache.set(ical_url, calendar_name, start_date, end_date, unique_events)

            return unique_events

        except Exception as e:
            console.print(f"  [red]✗[/red] Kunne ikke skrape {calendar_name}: {e}", style="red")
            import traceback
            traceback.print_exc()
            return []
