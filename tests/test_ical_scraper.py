"""Tests for the generic iCal calendar scraper (ical_scraper.py).

Covers:
  - feed-URL resolution for both Google-Calendar-style email IDs and full
    feed URLs (Teamup, Forumbooking, Bærum ishall, etc.) — the fix that was
    needed to support the new RVV clubs' real calendar sources.
  - end-to-end parsing of representative fixture iCal payloads (no live
    network access — `requests.get` is mocked).
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from tournament_scheduler.data_sources.ical_scraper import ICalScraper
from tournament_scheduler.utils.calendar_cache import CalendarCache


# A minimal but valid iCal feed with one tournament-keyword event and one
# practice (non-tournament) event, modelled after the kind of payload
# Teamup/Forumbooking/Google Calendar feeds return.
SAMPLE_ICAL_FEED = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test Calendar//EN
CALSCALE:GREGORIAN
BEGIN:VEVENT
UID:event-1@example.com
DTSTAMP:20260101T120000Z
DTSTART:20260615T100000Z
DTEND:20260615T130000Z
SUMMARY:Vinterturnering U10
LOCATION:Test Arena
END:VEVENT
BEGIN:VEVENT
UID:event-2@example.com
DTSTAMP:20260101T120000Z
DTSTART:20260616T180000Z
DTEND:20260616T200000Z
SUMMARY:Trening A-lag
LOCATION:Test Arena
END:VEVENT
END:VCALENDAR
"""


def _make_response(content, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.content = content
    return response


class TestFeedUrlResolution:
    """ICalScraper._feed_url resolves both Google-Calendar IDs and full feed URLs."""

    def test_email_style_calendar_id_expands_to_google_calendar_feed(self):
        scraper = ICalScraper("istiderskienhockey@gmail.com")
        assert scraper._feed_url() == (
            "https://calendar.google.com/calendar/ical/"
            "istiderskienhockey@gmail.com/public/basic.ics"
        )

    def test_https_url_is_used_as_is(self):
        url = "https://ics.teamup.com/feed/ksr8bg1tpn5s3npskw/0.ics"
        scraper = ICalScraper(url)
        assert scraper._feed_url() == url

    def test_http_url_is_used_as_is(self):
        url = "http://example.com/calendar.ics"
        scraper = ICalScraper(url)
        assert scraper._feed_url() == url

    def test_forumbooking_style_url_is_used_as_is_not_mangled(self):
        # Regression guard: previously any full URL passed as calendar_id was
        # mangled into an invalid Google Calendar address, e.g.
        # ".../ical/https://www.forumbooking.no/.../public/basic.ics".
        url = "https://www.forumbooking.no/ical.aspx?obj=2&schema=Jarhallen%20(ishall)"
        scraper = ICalScraper(url)
        feed_url = scraper._feed_url()
        assert feed_url == url
        assert "calendar.google.com" not in feed_url


class TestScrapeCalendarParsing:
    """scrape_calendar fetches, parses, filters, and caches iCal feed events."""

    def _scraper_with_empty_cache(self, calendar_id="https://example.com/feed.ics"):
        cache = MagicMock(spec=CalendarCache)
        cache.get.return_value = None
        return ICalScraper(calendar_id, cache=cache), cache

    def test_parses_events_within_date_range(self):
        scraper, cache = self._scraper_with_empty_cache()

        with patch(
            "tournament_scheduler.data_sources.ical_scraper.requests.get",
            return_value=_make_response(SAMPLE_ICAL_FEED),
        ):
            events = scraper.scrape_calendar(
                "https://example.com/feed.ics",
                "test calendar",
                datetime(2026, 6, 1),
                datetime(2026, 6, 30),
            )

        names = {event.name for event in events}
        assert "Vinterturnering U10" in names
        assert "Trening A-lag" in names
        assert len(events) == 2

    def test_returns_empty_list_on_non_200_response(self):
        scraper, cache = self._scraper_with_empty_cache()

        with patch(
            "tournament_scheduler.data_sources.ical_scraper.requests.get",
            return_value=_make_response(b"", status_code=404),
        ):
            events = scraper.scrape_calendar(
                "https://example.com/feed.ics",
                "test calendar",
                datetime(2026, 6, 1),
                datetime(2026, 6, 30),
            )

        assert events == []

    def test_returns_cached_events_without_fetching(self):
        cache = MagicMock(spec=CalendarCache)
        cached = [object()]
        cache.get.return_value = cached
        scraper = ICalScraper("https://example.com/feed.ics", cache=cache)

        with patch(
            "tournament_scheduler.data_sources.ical_scraper.requests.get"
        ) as mock_get:
            events = scraper.scrape_calendar(
                "https://example.com/feed.ics",
                "test calendar",
                datetime(2026, 6, 1),
                datetime(2026, 6, 30),
            )

        mock_get.assert_not_called()
        assert events is cached

    def test_caches_freshly_scraped_events(self):
        scraper, cache = self._scraper_with_empty_cache()

        with patch(
            "tournament_scheduler.data_sources.ical_scraper.requests.get",
            return_value=_make_response(SAMPLE_ICAL_FEED),
        ):
            events = scraper.scrape_calendar(
                "https://example.com/feed.ics",
                "test calendar",
                datetime(2026, 6, 1),
                datetime(2026, 6, 30),
            )

        assert cache.set.called
        cached_events_arg = cache.set.call_args[0][-1]
        assert cached_events_arg == events

    def test_handles_fetch_exceptions_gracefully(self):
        scraper, cache = self._scraper_with_empty_cache()

        with patch(
            "tournament_scheduler.data_sources.ical_scraper.requests.get",
            side_effect=RuntimeError("network exploded"),
        ):
            events = scraper.scrape_calendar(
                "https://example.com/feed.ics",
                "test calendar",
                datetime(2026, 6, 1),
                datetime(2026, 6, 30),
            )

        assert events == []
