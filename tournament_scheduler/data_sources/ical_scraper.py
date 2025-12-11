"""iCal-based calendar scraper for Google Calendar public feeds."""

import sys
import requests
from datetime import datetime, timedelta
from typing import List, Optional
from icalendar import Calendar as iCalendar
import recurring_ical_events
from tournament_scheduler.models import CalendarEvent
from tournament_scheduler.interfaces import CalendarScraper
from tournament_scheduler.utils.calendar_cache import CalendarCache


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
            print(f"  ✓ Using cached {calendar_name} calendar data ({len(cached_events)} events)\n", flush=True)
            return cached_events

        try:
            # Build iCal URL

            print(f"  Fetching {calendar_name} iCal feed...", flush=True)
            response = requests.get(ical_url, timeout=15)

            if response.status_code != 200:
                print(f"  ✗ Failed to fetch iCal feed: HTTP {response.status_code}", file=sys.stderr, flush=True)
                return events

            # Parse iCal data
            cal = iCalendar.from_ical(response.content)

            # Get events in date range
            # Add buffer to ensure we catch all events
            extended_end = end_date + timedelta(days=1)
            ical_events = recurring_ical_events.of(cal).between(start_date, extended_end)

            print(f"  Found {len(ical_events)} events in date range", flush=True)

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

            print(f"  ✓ Scraped {len(unique_events)} events from {calendar_name}\n", flush=True)

            # Cache the results
            self.cache.set(ical_url, calendar_name, start_date, end_date, unique_events)

            return unique_events

        except Exception as e:
            print(f"  ✗ Failed to scrape {calendar_name}: {e}\n", file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc()
            return []
