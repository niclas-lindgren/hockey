from datetime import date, datetime
from pathlib import Path

from tournament_scheduler.models import CalendarEvent, Roster, Team
from tournament_scheduler.rules_report import render_rules_markdown
from tournament_scheduler.scheduler import TournamentScheduler
from tournament_scheduler.season_planner import SeasonPlanner


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


def test_rules_report_markdown_matches_committed_doc():
    roster = Roster(
        teams=[
            Team(club="Jar", label="Jar U10", age_group="U10", skill_level=5),
            Team(club="Kongsberg", label="Kongsberg U10", age_group="U10", skill_level=6),
        ]
    )
    planner = SeasonPlanner(
        scheduler=FakeScheduler(),
        roster=roster,
        club_arenas={"Jar": "Jarhallen", "Kongsberg": "Kongsberghallen"},
        parallel_games_for_age_group={"U10": 3, "JU11": 2},
        events_by_club={
            "Jar": [
                CalendarEvent(
                    date="01.10.2026",
                    name="Jar hallbooking",
                    datetime=datetime(2026, 10, 1, 11, 0),
                    duration_hours=2.0,
                )
            ]
        },
    )

    expected = Path("docs/rvv-miniputt-rules-report.md").read_text(encoding="utf-8")
    generated = render_rules_markdown(planner)

    assert generated == expected
