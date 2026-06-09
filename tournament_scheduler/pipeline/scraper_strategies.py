"""Per-club scraper strategies that describe how to navigate each calendar system.

Each :class:`ScraperStrategy` tells the Pi-driven ScraperAgent how to interact
with a particular club's calendar site — what kind of page it is, what
navigation patterns to expect, and whether there's a simple deterministic
fallback (iframes, date params, iCal feed).

Strategies are organised by **calendar engine** since clubs using the same
platform (Bookup, Teamup, Forumbooking, Sportello) share the same navigation
patterns even though their URLs differ.

The ScraperAgent in the extension:
  1. Looks up the strategy for the current source
  2. Launches the Python browserWorker
  3. Uses Pi's model to evaluate page content and decide the next action
  4. Uses the strategy hints to guide the LLM

Sources with ``direct_ical`` or ``direct_iframe`` strategies can fall back to
the existing deterministic scraping in *stage2_scraping.py* when no LLM is
available.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CalendarEngine(str, Enum):
    """The booking/calendar platform a club's site uses."""

    OUTLOOK_IFRAME = "outlook_iframe"
    """Outlook Web Calendar rendered inside an iframe (Kongsberg)."""

    DATE_PARAM = "date_param"
    """Plain web page navigable via ?date=YYYY-MM-DD (Skien brp.exigo.no)."""

    TEAMUP_ICAL = "teamup_ical"
    """Teamup iCal feed — deterministic, no browser needed."""

    FORUMBOOKING = "forumbooking"
    """Forumbooking HTML schema viewer with JS month navigation (Jar)."""

    BOOKUP_SPA = "bookup_spa"
    """BookUp SPA with JS-rendered booking widget (Tønsberg, Sandefjord)."""

    SPORTELLO = "sportello"
    """Sportello booking widget SPA (Holmen)."""

    STYLED_CALENDAR = "styled_calendar"
    """StyledCalendar JS widget (Jutul / Bærum ishall)."""

    GENERIC_ICAL = "generic_ical"
    """Any other deterministic iCal feed."""


@dataclass
class ScraperStrategy:
    """Config describing how to scrape a club's calendar.

    Attributes
    ----------
    engine:
        The calendar system type.
    url:
        The base URL of the calendar.
    has_iframe:
        Whether the calendar content lives inside an ``<iframe>``.
    date_param:
        The query parameter name for date navigation (e.g. ``"date"``).
        Empty string means no date parameter.
    month_selector:
        Playwright selector for the "next month" button.
    event_pattern:
        Hint for the LLM about what event data looks like (free text).
    direct_ical_feed:
        If set, an iCal feed URL that can be used instead of browser scraping.
    direct_scraper:
        If true, the existing deterministic scraper can handle this source.
    initial_navigation:
        Optional list of actions to perform before scraping starts.
        Each action is a dict with ``cmd``, ``selector``, ``url``, etc.
    note:
        Free-text notes for the developer.
    """

    engine: CalendarEngine
    url: str
    has_iframe: bool = False
    date_param: str = ""
    month_selector: str = 'button[aria-label*="next month"]'
    event_pattern: str = ""
    direct_ical_feed: str | None = None
    direct_scraper: bool = False
    initial_navigation: list[dict[str, Any]] = field(default_factory=list)
    note: str = ""


# ---------------------------------------------------------------------------
# Strategy definitions per club
# ---------------------------------------------------------------------------

STRATEGIES: dict[str, ScraperStrategy] = {
    "Kongsberg": ScraperStrategy(
        engine=CalendarEngine.OUTLOOK_IFRAME,
        url="https://kongsberghallen.no/webkalender/ishall/",
        has_iframe=True,
        month_selector='button[aria-label*="next month"]',
        event_pattern="Outlook Web Calendar aria-label attributes",
        direct_scraper=True,
        note="Works with existing iframe-based deterministic scraper.",
    ),
    "Kongsberg ballhall": ScraperStrategy(
        engine=CalendarEngine.OUTLOOK_IFRAME,
        url="https://kongsberghallen.no/webkalender/ballhall-dagtid-og-helg/",
        has_iframe=True,
        month_selector='button[aria-label*="next month"]',
        event_pattern="Outlook Web Calendar aria-label attributes",
        direct_scraper=True,
        note="Works with existing iframe-based deterministic scraper.",
    ),
    "Skien": ScraperStrategy(
        engine=CalendarEngine.DATE_PARAM,
        url="https://skienfritidspark.brp.exigo.no/ishallen",
        date_param="date",
        month_selector="",
        event_pattern="Time ranges (HH:MM-HH:MM) in visible text",
        direct_scraper=True,
        note="Next.js app with ?date=YYYY-MM-DD navigation.",
    ),
    "Ringerike": ScraperStrategy(
        engine=CalendarEngine.TEAMUP_ICAL,
        url="https://ics.teamup.com/feed/ksr8bg1tpn5s3npskw/0.ics",
        direct_ical_feed="https://ics.teamup.com/feed/ksr8bg1tpn5s3npskw/0.ics",
        direct_scraper=True,
        note="Deterministic iCal feed — already integrated.",
    ),
    "Tønsberg": ScraperStrategy(
        engine=CalendarEngine.BOOKUP_SPA,
        url="https://www.bookup.no/utleie/Index/860",
        has_iframe=False,
        date_param="",
        month_selector="",
        event_pattern="",
        note="Bookup SPA med login-krav. Krever innlogging for å se kalenderen. Skraping ikke mulig uten autentisering.",
    ),
    "Sandefjord Penguins": ScraperStrategy(
        engine=CalendarEngine.BOOKUP_SPA,
        url="https://www.bookup.no/Utleie/#Bug%C3%A5rdshallen",
        has_iframe=False,
        date_param="",
        month_selector="",
        event_pattern="",
        note="Bookup SPA med login-krav. Krever innlogging for å se kalenderen. Skraping ikke mulig uten autentisering.",
    ),
    "Jar": ScraperStrategy(
        engine=CalendarEngine.FORUMBOOKING,
        url="https://www.forumbooking.no/schema.aspx?obj=2&schema=Jarhallen%20(ishall)&kalender=true&safarifix=true",
        has_iframe=False,
        month_selector="",
        event_pattern="",
        note="Forumbooking HTML schema viewer. Pi's model navigates the JS booking widget.",
    ),
    "Holmen": ScraperStrategy(
        engine=CalendarEngine.SPORTELLO,
        url="https://kalender.sportello.no/booking/11055",
        has_iframe=False,
        month_selector="",
        event_pattern="",
        note="Sportello SPA booking widget. Pi's model navigates.",
    ),
    "Jutul": ScraperStrategy(
        engine=CalendarEngine.STYLED_CALENDAR,
        url="https://baerumishall.no/kalender/",
        has_iframe=False,
        month_selector="",
        event_pattern="",
        note="StyledCalendar JS widget. Pi's model navigates the embedded calendar.",
    ),
    "Frisk Asker": ScraperStrategy(
        engine=CalendarEngine.TEAMUP_ICAL,
        url="https://teamup.com/ksdwpwxysmxwnuftoy",
        direct_ical_feed="https://ics.teamup.com/feed/ksdwpwxysmxwnuftoy/0.ics",
        direct_scraper=False,
        note="Teamup page — check if iCal feed URL pattern works. If not, use browser.",
    ),
}


def get_strategy(club_name: str) -> ScraperStrategy | None:
    """Look up the scraper strategy for a club by name."""
    return STRATEGIES.get(club_name)


def has_direct_scraper(strategy: ScraperStrategy) -> bool:
    """Whether this strategy can be handled by the existing deterministic scraper."""
    return strategy.direct_scraper or strategy.direct_ical_feed is not None


def needs_llm_agent(strategy: ScraperStrategy) -> bool:
    """Whether this strategy requires the Pi-driven LLM agent to scrape."""
    return not has_direct_scraper(strategy)


def list_strategies() -> dict[str, dict[str, Any]]:
    """Return a JSON-serialisable summary of all strategies."""
    return {
        name: {
            "engine": s.engine.value,
            "direct_scraper": s.direct_scraper,
            "direct_ical_feed": bool(s.direct_ical_feed),
            "has_iframe": s.has_iframe,
            "date_param": bool(s.date_param),
        }
        for name, s in STRATEGIES.items()
    }
