from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from tournament_scheduler.models import CalendarEvent, Roster, SchedulingResult, Team
from tournament_scheduler.pipeline.input_workbook import load_workbook_config
from tournament_scheduler.scheduler import TournamentScheduler
from tournament_scheduler.season_planner import SeasonPlanner


def canonical_input_path(path: str | Path | None = None) -> Path:
    """Return the canonical ``input.xlsx`` path used by docs/tests."""
    if path is not None:
        return Path(path)
    return Path(__file__).resolve().parents[2] / "input.xlsx"


def load_canonical_input_data(path: str | Path | None = None) -> dict[str, Any]:
    """Load the canonical workbook config from ``input.xlsx``."""
    return load_workbook_config(canonical_input_path(path))


def load_canonical_roster(path: str | Path | None = None) -> tuple[Roster, dict[str, int]]:
    """Load the canonical roster + per-age-group parallel-game config."""
    data = load_canonical_input_data(path)
    roster = Roster(teams=[Team(**team) for team in data["teams"]])
    return roster, data.get("parallel_games", {})


def load_canonical_season_window(path: str | Path | None = None) -> tuple[datetime, datetime]:
    """Load the canonical season start/end from ``input.xlsx``."""
    data = load_canonical_input_data(path)
    return (
        datetime.fromisoformat(data["start_date"]),
        datetime.fromisoformat(data["end_date"]),
    )


def all_weekend_dates(start: datetime, end: datetime) -> list[date]:
    """Return all Saturday/Sunday dates inside a season window."""
    dates: list[date] = []
    current = start.date()
    while current <= end.date():
        if current.weekday() in (5, 6):
            dates.append(current)
        current += timedelta(days=1)
    return dates


class OfflineScheduler:
    """Deterministic scheduler for canonical tests with no calendar I/O."""

    def __init__(self, free_dates: list[date]):
        self.free_dates = free_dates
        self._real_scheduler = TournamentScheduler(
            calendar_sources=[], conflict_checkers=[], date_parser=None
        )

    def find_available_dates(self, start_date, end_date, **kwargs):
        return SchedulingResult(
            available_dates=list(self.free_dates),
            excluded_dates=[],
            exclusion_breakdown={},
            detailed_exclusions=[],
            total_weekends_checked=len(self.free_dates),
        )

    def find_arena_slot_for_date(
        self,
        check_date,
        host_club,
        required_minutes,
        events_by_club,
        preferred_start="11:00",
    ):
        return self._real_scheduler.find_arena_slot_for_date(
            check_date,
            host_club,
            required_minutes,
            events_by_club,
            preferred_start=preferred_start,
        )


def build_canonical_planner(
    path: str | Path | None = None,
    *,
    events_by_club: dict[str, list[CalendarEvent]] | None = None,
    free_dates: list[date] | None = None,
    **planner_kwargs: Any,
) -> tuple[SeasonPlanner, datetime, datetime]:
    """Build a SeasonPlanner from the canonical ``input.xlsx`` test fixture."""
    roster, parallel_games = load_canonical_roster(path)
    start, end = load_canonical_season_window(path)
    clubs = sorted({team.club for team in roster.teams})
    planner = SeasonPlanner(
        scheduler=OfflineScheduler(free_dates or all_weekend_dates(start, end)),
        roster=roster,
        club_arenas={club: f"{club}hallen" for club in clubs},
        parallel_games_for_age_group=parallel_games,
        events_by_club=events_by_club or {},
        **planner_kwargs,
    )
    return planner, start, end
