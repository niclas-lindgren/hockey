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

Known sources today: Kongsberg, Skien, Jutul, Jar, Ringerike.
Still missing (need URLs before they can be scraped live): Holmen, Frisk Asker,
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
        source="https://teamup.com/ksr8bg1tpn5s3npskw",
        note="Teamup calendar feed.",
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
        arena="Askerhallen",
        kind=CalendarSourceKind.UNKNOWN,
        source=None,
        skip=True,
        note="TODO: calendar URL not yet provided — add a registry entry once known.",
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
        source=(
            "https://www.forumbooking.no/schema.aspx?obj=2&schema=Jarhallen%20(ishall)"
            "&kalender=true&safarifix=true"
        ),
        note="Forumbooking calendar feed (iCal-compatible).",
    ),
    "Holmen": ClubCalendarSource(
        club="Holmen",
        arena="Holmenkollen ishall",
        kind=CalendarSourceKind.UNKNOWN,
        source=None,
        skip=True,
        note="TODO: calendar URL not yet provided — add a registry entry once known.",
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
        source="https://baerumishall.no/kalender/",
        note="Bærum ishall calendar feed.",
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


def build_data_source(entry: ClubCalendarSource):
    """Construct the appropriate CalendarDataSource for a registry entry.

    For OUTLOOK sources this builds an `IceHallCalendar` backed by a shared
    `CalendarScraper` (Playwright/Outlook-based webkalender).
    For ICAL sources this builds an `IceHallCalendar` backed by an `ICalScraper`
    constructed from the entry's `source` (calendar_id or feed URL), matching
    the existing Skien integration pattern.

    Returns None for UNKNOWN/skip entries.
    """
    if not entry.is_known:
        return None

    from tournament_scheduler.data_sources.ice_hall_calendar import IceHallCalendar

    if entry.kind == CalendarSourceKind.OUTLOOK:
        from tournament_scheduler.data_sources.calendar_scraper import CalendarScraper

        return IceHallCalendar(entry.source, CalendarScraper())

    if entry.kind == CalendarSourceKind.ICAL:
        from tournament_scheduler.data_sources.ical_scraper import ICalScraper

        return IceHallCalendar(entry.source, ICalScraper(entry.source))

    return None
