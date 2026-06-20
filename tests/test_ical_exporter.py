"""Tests for ICalExporter.export_tournament_summary()."""

from datetime import date

from icalendar import Calendar

from tournament_scheduler.ical.ical_exporter import ICalExporter
from tournament_scheduler.models import Game, SeasonPlan, Team, Tournament


def test_one_vevent_per_tournament(tmp_path):
    """export_tournament_summary() should produce one VEVENT per tournament, not per game."""
    team1 = Team("ClubA", "TeamA", "U10")
    team2 = Team("ClubB", "TeamB", "U10")
    team3 = Team("ClubC", "TeamC", "U10")
    team4 = Team("ClubD", "TeamD", "U10")

    game1 = Game(team1, team2, 1, 1)
    game2 = Game(team3, team4, 2, 1)

    tournament1 = Tournament(date(2025, 1, 4), "Arena1", "U10", games=[game1, game2])
    tournament2 = Tournament(date(2025, 1, 11), "Arena2", "U10", games=[game1, game2])

    plan = SeasonPlan([tournament1, tournament2])

    output_path = tmp_path / "test_export.ics"
    ICalExporter().export_tournament_summary(plan, output_path)

    with open(output_path, "rb") as f:
        calendar = Calendar.from_ical(f.read())

    vevents = list(calendar.walk("vevent"))
    assert len(vevents) == 2, f"Expected 2 VEVENTs (one per tournament), got {len(vevents)}"


def test_description_contains_team_names(tmp_path):
    """VEVENT DESCRIPTION should contain the labels of all participating teams."""
    team1 = Team("ClubA", "Alpha U10", "U10")
    team2 = Team("ClubB", "Beta U10", "U10")

    game = Game(team1, team2, 1, 1)
    tournament = Tournament(date(2025, 1, 4), "Arena1", "U10", games=[game])

    plan = SeasonPlan([tournament])
    output_path = tmp_path / "test_export.ics"
    ICalExporter().export_tournament_summary(plan, output_path)

    with open(output_path, "rb") as f:
        calendar = Calendar.from_ical(f.read())

    vevent = list(calendar.walk("vevent"))[0]
    description = str(vevent.get("description", ""))
    assert "Alpha U10" in description
    assert "Beta U10" in description


def test_description_contains_vs_pairing(tmp_path):
    """VEVENT DESCRIPTION should contain 'home vs away' matchup pairings."""
    team1 = Team("ClubA", "Alpha U10", "U10")
    team2 = Team("ClubB", "Beta U10", "U10")

    game = Game(team1, team2, 1, 1)
    tournament = Tournament(date(2025, 1, 4), "Arena1", "U10", games=[game])

    plan = SeasonPlan([tournament])
    output_path = tmp_path / "test_export.ics"
    ICalExporter().export_tournament_summary(plan, output_path)

    with open(output_path, "rb") as f:
        calendar = Calendar.from_ical(f.read())

    vevent = list(calendar.walk("vevent"))[0]
    description = str(vevent.get("description", ""))
    assert "Alpha U10 vs Beta U10" in description


def test_no_kamper_section_when_no_games(tmp_path):
    """VEVENT DESCRIPTION should not include a 'Kamper:' section when tournament has no games."""
    team1 = Team("ClubA", "Alpha U10", "U10")
    team2 = Team("ClubB", "Beta U10", "U10")

    tournament = Tournament(date(2025, 1, 4), "Arena1", "U10", teams=[team1, team2], games=[])

    plan = SeasonPlan([tournament])
    output_path = tmp_path / "test_export.ics"
    ICalExporter().export_tournament_summary(plan, output_path)

    with open(output_path, "rb") as f:
        calendar = Calendar.from_ical(f.read())

    vevent = list(calendar.walk("vevent"))[0]
    description = str(vevent.get("description", ""))
    assert "Kamper:" not in description
