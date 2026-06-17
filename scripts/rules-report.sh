#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

python3 - <<'PY'
from datetime import datetime
from pathlib import Path

from tournament_scheduler.models import CalendarEvent
from tournament_scheduler.rules_report import render_rules_markdown
from tournament_scheduler.scheduler import TournamentScheduler
from tournament_scheduler.season_planner import SeasonPlanner
from tournament_scheduler.testing.canonical_input import load_canonical_roster


class FakeScheduler:
    def __init__(self):
        self._real_scheduler = TournamentScheduler(calendar_sources=[], conflict_checkers=[], date_parser=None)

    def find_available_dates(self, start_date, end_date, **kwargs):
        from tournament_scheduler.models import SchedulingResult

        return SchedulingResult(
            available_dates=[],
            excluded_dates=[],
            exclusion_breakdown={},
            detailed_exclusions=[],
            total_weekends_checked=0,
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


roster, parallel_games = load_canonical_roster()
clubs = sorted({team.club for team in roster.teams})
planner = SeasonPlanner(
    scheduler=FakeScheduler(),
    roster=roster,
    club_arenas={club: f"{club}hallen" for club in clubs},
    parallel_games_for_age_group=parallel_games,
    events_by_club={
        clubs[0]: [
            CalendarEvent(
                date="01.10.2026",
                name=f"{clubs[0]} hallbooking",
                datetime=datetime(2026, 10, 1, 11, 0),
                duration_hours=2.0,
            )
        ]
    },
)

Path("docs/rvv-miniputt-rules-report.md").write_text(render_rules_markdown(planner), encoding="utf-8")
PY

python3 -m pytest tests/test_rules_report_doc.py tests/test_season_planner.py -q
