"""Central registry of Region Viken Vest (RVV) clubs and their calendar sources.

This module maps each of the nine RVV clubs (https://www.rvvhockey.no/) to the
right calendar data-source construction so the rest of the pipeline (season
planner, conflict checkers, etc.) can simply look a club up by name instead of
re-deriving URLs / scraper types inline.

Each entry records:
  - the club's home arena name (used by the season planner to verify that
    every arena gets at least one tournament)
  - the kind of calendar source ("outlook" for Outlook/Playwright-based ice
    halls via `IceHallCalendar` + `CalendarScraper`, "ical" for generic iCal
    feeds via `ICalScraper`, or "unknown" where no source URL/ID is known yet)
  - the URL (for "outlook"/generic feeds) or calendar_id (for "ical")
  - a `skip` flag for clubs that cannot yet be scraped, so the rest of the
    pipeline can simply filter them out and continue working for the clubs
    with known sources.

Known/working sources today: Kongsberg, Skien, Ringerike (Teamup iCal export).

Registered but not yet scrapeable live (kind is known but the feed needs more
work — see notes on each entry):
  - Jutul: baerumishall.no/kalender/ embeds a StyledCalendar JS widget with no
    discoverable .ics/iCal export.
  - Jar: Forumbooking's ical.aspx export returns only an empty placeholder
    VEVENT regardless of date-range params.
  - Frisk Asker: friskaskerhockey.no ("Aktivitetskalender") is a JS-rendered
    Sportality/s8y SPA with no static calendar markup or export API found;
    varnerarena.no is blocked by a WAF page.
  - Holmen: holmenhockey.no links to a Sportello booking widget
    (kalender.sportello.no/booking/11055) that is a JS-rendered SPA shell with
    no discoverable .ics/iCal export.

All four of the above would need either a discovered platform-specific export
API (Sportello / Sportality·s8y / StyledCalendar) or a Playwright-based scraper
for their JS-rendered booking widgets — analogous to Kongsberg's OUTLOOK
integration but for different platforms/markup.

Still missing URLs entirely (no calendar/booking system identified at all):
Tønsberg, Sandefjord Penguins.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class CalendarSourceKind(Enum):
    """The kind of calendar data source a club uses."""

    # Outlook/Playwright-based webkalender, consumed via IceHallCalendar(url, CalendarScraper())
    OUTLOOK = "outlook"
    # Generic iCal feed (Google Calendar, Forumbooking, Teamup, etc.), consumed via ICalScraper(calendar_id)
    ICAL = "ical"
    # No known calendar source yet — registry entry exists as a documented placeholder
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ClubCalendarSource:
    """Registry entry describing how to build a calendar data source for a club."""

    club: str
    arena: str
    kind: CalendarSourceKind
    # For OUTLOOK / generic-feed sources: the calendar URL.
    # For ICAL sources: the calendar_id (e.g. a Google Calendar email-style ID, or feed URL).
    source: Optional[str] = None
    # True when no usable source is known yet — pipeline should skip this club
    # rather than fail, and surface a TODO so the source can be added later.
    skip: bool = False
    note: Optional[str] = None

    @property
    def is_known(self) -> bool:
        """Whether this club has a usable, known calendar source today."""
        return not self.skip and self.source is not None


# The nine RVV clubs. Order follows the PROJECT.md / plan listing.
CLUB_REGISTRY: Dict[str, ClubCalendarSource] = {
    "Ringerike": ClubCalendarSource(
        club="Ringerike",
        arena="Ringerikshallen",
        kind=CalendarSourceKind.ICAL,
        # The public calendar page (https://teamup.com/ksr8bg1tpn5s3npskw) is an
        # HTML/JS view, not a feed — Teamup exposes the actual iCal export at
        # ics.teamup.com using the same calendar key (verified: returns
        # text/calendar with hundreds of parseable VEVENTs).
        source="https://ics.teamup.com/feed/ksr8bg1tpn5s3npskw/0.ics",
        note="Teamup iCal export feed (verified working — confirm parses via icalendar/recurring_ical_events).",
    ),
    "Tønsberg": ClubCalendarSource(
        club="Tønsberg",
        arena="Tønsberghallen",
        kind=CalendarSourceKind.UNKNOWN,
        source=None,
        skip=True,
        note="TODO: calendar URL not yet provided — add a registry entry once known.",
    ),
    "Frisk Asker": ClubCalendarSource(
        club="Frisk Asker",
        # Home arena is "Varner Arena" (Frisk Asker's official site refers to it
        # this way), not "Askerhallen" as previously assumed.
        arena="Varner Arena",
        kind=CalendarSourceKind.UNKNOWN,
        # https://www.friskaskerhockey.no/ ("Frisk Asker Ishockey") has an
        # "Aktivitetskalender" page, but the whole site is a JS-rendered SPA
        # (built on the Sportality/s8y platform — assets served from
        # cdn.s8y.se) with no static HTML calendar markup or any discoverable
        # .ics/iCal export endpoint (checked /api/calendar -> 404 JSON,
        # /aktivitetskalender and /kalender both just return the same SPA
        # shell). varnerarena.no itself is behind a "RUNCLOUD-7G-WAF-BLOCKED"
        # WAF page and could not be inspected. Forumbooking does NOT host a
        # "Varner Arena"/"Askerhallen" schema (its schema.aspx ignores unknown
        # `schema` values and silently falls back to Jarhallen's data).
        source=None,
        skip=True,
        note=(
            "Checked: friskaskerhockey.no (Sportality/s8y JS SPA — "
            "'Aktivitetskalender' page exists but renders client-side with no "
            "static calendar markup or .ics export found; /api/calendar -> 404), "
            "varnerarena.no (blocked by a WAF/'RUNCLOUD-7G-WAF-BLOCKED' page), "
            "and Forumbooking (no 'Varner Arena'/'Askerhallen' schema — query "
            "param is ignored, falls back to Jarhallen). A live, working source "
            "would need either a discovered Sportality calendar API or a "
            "Playwright-based scraper for the SPA (similar to Kongsberg's "
            "OUTLOOK integration, but for a different platform/markup). "
            "No new scraper code is needed to wire it in once found — "
            "build_calendar_source() already builds an IceHallCalendar from "
            "either an ICAL feed URL (-> ICalScraper) or an OUTLOOK webkalender "
            "URL (-> OutlookCalendarScraper); just set kind/source/skip=False."
        ),
    ),
    "Sandefjord Penguins": ClubCalendarSource(
        club="Sandefjord Penguins",
        arena="Sandefjord ishall",
        kind=CalendarSourceKind.UNKNOWN,
        source=None,
        skip=True,
        note=(
            "TODO: calendar URL not yet provided. Sandefjord already appears as an "
            "opponent in existing_schedule/U10_ETTER_JUL_Klar_-_Kongsberg_Sandefjord.xlsx "
            "but has no live calendar scraper yet."
        ),
    ),
    "Jar": ClubCalendarSource(
        club="Jar",
        arena="Jarhallen",
        kind=CalendarSourceKind.ICAL,
        # The schema.aspx URL is the HTML calendar viewer, not a feed.
        # Forumbooking (FRI Webb-Bokning) exposes ical.aspx as an export
        # endpoint, but as of this check it returns a single empty placeholder
        # VEVENT (DTSTART/SUMMARY/UID all blank) regardless of date-range
        # query params (from/to, start/end, dateFrom/dateTo) — the booking
        # system likely requires session/auth or a different export trigger
        # to populate real events.
        source="https://www.forumbooking.no/ical.aspx?obj=2&schema=Jarhallen%20(ishall)",
        skip=True,
        note=(
            "TODO: Forumbooking ical.aspx export currently returns an empty "
            "placeholder VEVENT (no usable DTSTART/SUMMARY) — needs further "
            "investigation (auth/session/export trigger) before this club can "
            "be scraped live. Pipeline skips it for now."
        ),
    ),
    "Holmen": ClubCalendarSource(
        club="Holmen",
        arena="Holmenkollen ishall",
        kind=CalendarSourceKind.UNKNOWN,
        # holmenhockey.no ("Holmen Hockey") has an "istider" (ice times) page
        # and links to a Sportello booking widget
        # (https://kalender.sportello.no/booking/11055), but that widget is a
        # JS-rendered SPA shell (~1.3KB HTML) — every export-style URL pattern
        # tried (.ics, /ical/, /export/*.ics, /booking/*/ical, /feed/*.ics)
        # returns the identical SPA shell rather than calendar data, and no
        # .ics/iCal link is exposed in the static markup. The /istider page
        # itself is a static text page (training-time table), not a calendar
        # feed.
        source=None,
        skip=True,
        note=(
            "Checked: holmenhockey.no/istider (static training-times text page, "
            "not a calendar feed) and the linked Sportello booking widget at "
            "kalender.sportello.no/booking/11055 (JS-rendered SPA shell — every "
            "guessed export URL pattern returns the same ~1.3KB shell, no "
            ".ics/iCal export discoverable in static markup; its JS bundle "
            "(assets/index.0f99a841.js) has no inlined API base URL either). "
            "A live source would need a discovered Sportello calendar/export "
            "API or a Playwright-based scraper for the booking widget. "
            "No new scraper code is needed to wire it in once found — "
            "build_calendar_source() already builds an IceHallCalendar from "
            "either an ICAL feed URL (-> ICalScraper) or an OUTLOOK webkalender "
            "URL (-> OutlookCalendarScraper); just set kind/source/skip=False."
        ),
    ),
    "Skien": ClubCalendarSource(
        club="Skien",
        arena="Skien ishall",
        kind=CalendarSourceKind.ICAL,
        source="istiderskienhockey@gmail.com",
        note="Google Calendar public iCal feed (existing integration).",
    ),
    "Jutul": ClubCalendarSource(
        club="Jutul",
        arena="Bærum ishall",
        kind=CalendarSourceKind.ICAL,
        # https://baerumishall.no/kalender/ is an HTML page embedding a
        # StyledCalendar JS widget (iframe to embed.styledcalendar.com) — no
        # static .ics/iCal export endpoint could be found for it, so a generic
        # ICalScraper cannot consume it as-is. It would need a Playwright-based
        # (OUTLOOK-style) scraper or a discovered StyledCalendar export API.
        source="https://baerumishall.no/kalender/",
        skip=True,
        note=(
            "TODO: baerumishall.no/kalender/ embeds a StyledCalendar JS widget "
            "with no exposed iCal/.ics feed — a generic ICalScraper cannot "
            "parse it. Needs a Playwright-based scraper (like Kongsberg's "
            "OUTLOOK integration) or a discovered StyledCalendar export API "
            "before this club can be scraped live. Pipeline skips it for now."
        ),
    ),
    "Kongsberg": ClubCalendarSource(
        club="Kongsberg",
        arena="Kongsberghallen",
        kind=CalendarSourceKind.OUTLOOK,
        source="https://kongsberghallen.no/webkalender/ishall/",
        note="Outlook/Playwright-based webkalender (existing integration). Also has a ball hall calendar.",
    ),
}


def get_club(name: str) -> ClubCalendarSource:
    """Look up a club's registry entry by name.

    Raises KeyError with a helpful message if the club is not in the registry.
    """
    try:
        return CLUB_REGISTRY[name]
    except KeyError:
        raise KeyError(
            f"Unknown club '{name}'. Known clubs: {', '.join(sorted(CLUB_REGISTRY))}"
        )


def known_clubs() -> List[ClubCalendarSource]:
    """Return registry entries for clubs with a usable, known calendar source."""
    return [entry for entry in CLUB_REGISTRY.values() if entry.is_known]


def missing_clubs() -> List[ClubCalendarSource]:
    """Return registry entries for clubs that are missing a calendar source (skip=True)."""
    return [entry for entry in CLUB_REGISTRY.values() if entry.skip]


def build_data_source(entry: ClubCalendarSource, cache=None):
    """Construct the appropriate CalendarDataSource for a registry entry.

    Thin wrapper around the registry-driven
    `data_sources.calendar_source_factory.build_calendar_source`, kept here for
    backward compatibility with existing callers/tests that import
    `build_data_source` from `club_registry`.

    For OUTLOOK sources this builds an `IceHallCalendar` backed by a shared
    `OutlookCalendarScraper` (Playwright-based webkalender).
    For ICAL sources this builds an `IceHallCalendar` backed by an `ICalScraper`
    constructed from the entry's `source` (calendar_id or feed URL), matching
    the existing Skien integration pattern.

    Args:
        entry: The club's `ClubCalendarSource` registry entry.
        cache: Optional shared `CalendarCache` to back the underlying scraper.

    Returns None for UNKNOWN/skip entries.
    """
    from tournament_scheduler.data_sources.calendar_source_factory import build_calendar_source

    return build_calendar_source(entry, cache)
