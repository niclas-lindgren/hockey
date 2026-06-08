"""Registry-driven factory for building calendar data sources for RVV clubs.

This module centralises the mapping from a `ClubCalendarSource` registry entry
(`tournament_scheduler.club_registry`) to the concrete, scraper-backed
`CalendarDataSource` instance the rest of the pipeline (season planner,
conflict checkers, scheduling command, etc.) actually consumes.

It replaces the ad-hoc, hardcoded instantiation previously seen in
`scheduling_command.py`:

    scraper = CalendarScraper()
    kongsberg = get_club("Kongsberg")
    IceHallCalendar(kongsberg.source, scraper)

Both `CalendarSourceKind.OUTLOOK` and `CalendarSourceKind.ICAL` entries are
wired through `IceHallCalendar` so that tournament-keyword filtering stays
consistent across every club:

  - OUTLOOK -> IceHallCalendar(entry.source, OutlookCalendarScraper(cache))
  - ICAL    -> IceHallCalendar(entry.source, ICalScraper(entry.source, cache))

`UNKNOWN` and `skip=True` entries have no usable source yet; `build_calendar_source`
returns `None` for them so callers can simply skip those clubs (mirroring
`ClubCalendarSource.is_known` / `club_registry.missing_clubs`).
"""

from typing import Optional

from tournament_scheduler.club_registry import CalendarSourceKind, ClubCalendarSource
from tournament_scheduler.interfaces import CalendarDataSource
from tournament_scheduler.utils.calendar_cache import CalendarCache


def build_calendar_source(
    entry: ClubCalendarSource, cache: Optional[CalendarCache] = None
) -> Optional[CalendarDataSource]:
    """Build the appropriate calendar data source for a club registry entry.

    Args:
        entry: The club's `ClubCalendarSource` registry entry.
        cache: Optional shared `CalendarCache` to back the underlying scraper.
            When omitted, each scraper falls back to its own default cache.

    Returns:
        A `CalendarDataSource`-compatible instance (currently always an
        `IceHallCalendar` wrapping the kind-appropriate scraper), or `None`
        for `UNKNOWN`/`skip=True` entries that have no usable source yet.

    Raises:
        ValueError: if `entry.kind` is a recognised, "known" kind that this
            factory does not yet know how to build (defensive guard against
            registry/factory drift — should not happen in practice since
            `OUTLOOK` and `ICAL` are the only kinds that can be `is_known`).
    """
    if not entry.is_known:
        return None

    # Imported lazily to avoid pulling in Playwright/iCal dependencies for
    # callers that only need the registry (mirrors club_registry.build_data_source).
    from tournament_scheduler.data_sources.calendar_scraper import OutlookCalendarScraper
    from tournament_scheduler.data_sources.ical_scraper import ICalScraper
    from tournament_scheduler.data_sources.ice_hall_calendar import IceHallCalendar

    if entry.kind == CalendarSourceKind.OUTLOOK:
        return IceHallCalendar(entry.source, OutlookCalendarScraper(cache))

    if entry.kind == CalendarSourceKind.ICAL:
        return IceHallCalendar(entry.source, ICalScraper(entry.source, cache))

    raise ValueError(
        f"No calendar source factory wired up for kind={entry.kind!r} "
        f"(club={entry.club!r}). Known kinds: OUTLOOK, ICAL."
    )
