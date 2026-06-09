"""iCal exporter — writes one VEVENT per game in a SeasonPlan.

Uses the ``icalendar`` library (already in requirements.txt) to produce a
standards-compliant ``.ics`` file that can be imported into any calendar app.

Each VEVENT uses:
- ``DTSTART`` / ``DTEND``: tournament date at 09:00 + 1 h per game slot
  (rough placeholder since exact game times are not in the model yet)
- ``SUMMARY``: "<home> vs <away>"
- ``LOCATION``: arena name
- ``CATEGORIES``: age group
"""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from icalendar import Calendar, Event, vText

from ..models import SeasonPlan, Tournament, Game


# ---------------------------------------------------------------------------
# Exporter
# ---------------------------------------------------------------------------


class ICalExporter:
    """Export a :class:`~tournament_scheduler.models.SeasonPlan` to an iCal file.

    Parameters
    ----------
    game_duration_minutes:
        Duration of a single game in minutes (default 60).
    start_hour:
        Hour of day (0-23) when the first game of a tournament day starts.
    """

    def __init__(
        self,
        game_duration_minutes: int = 60,
        start_hour: int = 9,
    ) -> None:
        self.game_duration_minutes = game_duration_minutes
        self.start_hour = start_hour

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export(self, plan: SeasonPlan, output_path: str | os.PathLike[str]) -> str:
        """Write the plan to an ``.ics`` file at *output_path*.

        Returns the path written (as a string) so callers can log it.
        """
        cal = self._build_calendar(plan)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(cal.to_ical())
        return str(path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_calendar(self, plan: SeasonPlan) -> Calendar:
        cal = Calendar()
        cal.add("prodid", "-//Kongsberg Hockey Scheduler//NO")
        cal.add("version", "2.0")
        cal.add("calscale", "GREGORIAN")
        cal.add("x-wr-calname", vText("RVV Sesongplan"))

        for tournament in plan.tournaments:
            for event in self._tournament_events(tournament):
                cal.add_component(event)

        return cal

    def _tournament_events(self, tournament: Tournament) -> list[Event]:
        """Generate one VEVENT per game in the tournament."""
        events: list[Event] = []
        games = list(tournament.games)

        # Group by parallel slot to assign wall-clock times
        # parallel_slot 0 means all games in one slot (sequential)
        # Build a mapping: slot_index → [games]
        slot_map: dict[int, list[Game]] = {}
        for game in games:
            slot = game.parallel_slot
            slot_map.setdefault(slot, []).append(game)

        # Assign times: slot 0 starts at start_hour, each new slot adds duration
        unique_slots = sorted(slot_map.keys())
        slot_start_offsets = {slot: i for i, slot in enumerate(unique_slots)}

        game_dur = timedelta(minutes=self.game_duration_minutes)

        for game in games:
            slot = game.parallel_slot
            offset_slots = slot_start_offsets.get(slot, 0)
            dt_start = datetime(
                tournament.date.year,
                tournament.date.month,
                tournament.date.day,
                self.start_hour,
                0,
                0,
                tzinfo=timezone.utc,
            ) + game_dur * offset_slots

            dt_end = dt_start + game_dur

            event = Event()
            event.add("uid", str(uuid.uuid4()))
            event.add("summary", vText(f"{game.home.label} vs {game.away.label}"))
            event.add("dtstart", dt_start)
            event.add("dtend", dt_end)
            event.add("location", vText(tournament.arena))
            event.add("categories", [tournament.age_group])
            event.add("description", vText(
                f"Turnering: {tournament.arena} | {tournament.age_group}"
            ))
            events.append(event)

        return events
