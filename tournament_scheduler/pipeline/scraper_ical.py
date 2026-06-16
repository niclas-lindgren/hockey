"""iCal scraper wrapper for Stage 2."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..models import CalendarEvent
from ..utils.calendar_cache import CalendarCache


def _run_ical_scraper(
    url: str,
    name: str,
    start_date: datetime,
    end_date: datetime,
    source_type: str,
    cache: CalendarCache | None = None,
) -> list[CalendarEvent]:
    """Run the iCal scraper for ``ical`` and ``google`` source types.

    Both use :class:`ICalScraper` (HTTP-fetched iCal feeds). The ``url`` may
    be a full feed URL (https://ics.teamup.com/...) or a Google Calendar
    email-style ID (``name@gmail.com``) which ``ICalScraper`` expands into the
    public Google Calendar iCal feed URL automatically.
    """
    from ..data_sources.ical_scraper import ICalScraper

    scraper = ICalScraper(url, cache=cache)
    return scraper.scrape_calendar(url, name, start_date, end_date)
