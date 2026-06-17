from datetime import datetime
from pathlib import Path

from tournament_scheduler.models import CalendarEvent
from tournament_scheduler.rules_report import render_rules_markdown
from tournament_scheduler.testing.canonical_input import build_canonical_planner


def test_rules_report_markdown_matches_committed_doc(canonical_input_data):
    clubs = sorted({team["club"] for team in canonical_input_data["teams"]})
    planner, _, _ = build_canonical_planner(
        events_by_club={
            clubs[0]: [
                CalendarEvent(
                    date="01.10.2026",
                    name=f"{clubs[0]} hallbooking",
                    datetime=datetime(2026, 10, 1, 11, 0),
                    duration_hours=2.0,
                )
            ]
        }
    )

    expected = Path("docs/rvv-miniputt-rules-report.md").read_text(encoding="utf-8")
    generated = render_rules_markdown(planner)

    assert generated == expected
