"""Event serialisation and grouping helpers for Stage 2 scraping.

Provides :func:`_events_to_dicts` for serialising :class:`CalendarEvent` objects
to plain JSON-compatible dicts, and :func:`_group_events_by_club` for mapping
per-source results to RVV club names.
"""

from __future__ import annotations

from typing import Any

from ..club_registry import club_for_source_name
from ..models import CalendarEvent


def _events_to_dicts(events: list[CalendarEvent]) -> list[dict[str, Any]]:
    """Serialise :class:`CalendarEvent` objects to plain dicts for JSON output."""
    result = []
    for e in events:
        result.append(
            {
                "date": e.date,
                "name": e.name,
                "datetime": e.datetime.isoformat(),
                "duration_hours": e.duration_hours,
            }
        )
    return result


def _group_events_by_club(
    source_results: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Group already-serialised source events by RVV club name.

    Each entry in *source_results* has a ``"name"`` (the Stage 1 source name,
    e.g. ``"Kongsberg ishall"`` or ``"Frisk Asker"``) and an ``"events"`` list
    of event dicts (as produced by :func:`_events_to_dicts`). This maps each
    source's events to the matching :data:`CLUB_REGISTRY` club name (via
    :func:`club_for_source_name`) so downstream code can look up
    "all events for Frisk Asker's Varner Arena" without re-filtering the flat
    per-source list.

    Sources that don't match any known club (or carry no events) are simply
    omitted -- existing flat-list (``"sources"``) consumers are unaffected.
    """
    by_club: dict[str, list[dict[str, Any]]] = {}
    for source_result in source_results:
        source_name = source_result.get("name", "")
        club_name = club_for_source_name(source_name)
        if club_name is None:
            continue
        events = source_result.get("events", [])
        if not events:
            continue
        by_club.setdefault(club_name, []).extend(events)
    return by_club
