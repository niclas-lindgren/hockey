"""Tests for SeasonPlanExporter (Excel export of season plans)."""

from datetime import date

import openpyxl
import pytest

from tournament_scheduler.models import Game, SeasonPlan, Team, Tournament
from tournament_scheduler.excel.plan_exporter import SeasonPlanExporter, _NORWEGIAN_WEEKDAYS


def _round_robin_games(teams):
    games = []
    for i in range(len(teams)):
        for j in range(i + 1, len(teams)):
            games.append(Game(home=teams[i], away=teams[j], parallel_slot=(i + j) % 2))
    return games


@pytest.fixture
def sample_plan():
    teams_u10 = [Team(club=f"Club{i}", label=f"U10-{i}", age_group="U10") for i in range(5)]
    teams_ju11 = [Team(club=f"Club{i}", label=f"JU11-{i}", age_group="JU11") for i in range(4)]

    t1 = Tournament(
        date=date(2026, 10, 10),
        arena="Jarhallen",
        age_group="U10",
        teams=teams_u10,
        games=_round_robin_games(teams_u10),
        host_club="Jar",
    )
    t2 = Tournament(
        date=date(2026, 11, 7),
        arena="Bærum ishall",
        age_group="JU11",
        teams=teams_ju11,
        games=_round_robin_games(teams_ju11),
        host_club="Jutul",
    )
    return SeasonPlan(
        tournaments=[t1, t2],
        start_date=date(2026, 10, 1),
        end_date=date(2027, 4, 30),
        diversity_score=0.5,
        arena_counts={"Jarhallen": 1, "Bærum ishall": 1},
    )


class TestSeasonPlanExporter:
    """Test suite for SeasonPlanExporter.export — round-trips through openpyxl."""

    def test_export_writes_a_readable_workbook(self, sample_plan, tmp_path):
        output_path = tmp_path / "season_plan.xlsx"
        SeasonPlanExporter().export(sample_plan, str(output_path))

        assert output_path.exists()

        workbook = openpyxl.load_workbook(str(output_path))
        assert "Sesongoversikt" in workbook.sheetnames
        # One sheet per tournament, plus the overview sheet, plus one summary
        # sheet per distinct club appearing in the plan's rosters.
        distinct_clubs = {team.club for tournament in sample_plan.tournaments for team in tournament.teams}
        assert len(workbook.sheetnames) == 1 + len(sample_plan.tournaments) + len(distinct_clubs)

    def test_overview_rows_match_plan_tournaments(self, sample_plan, tmp_path):
        output_path = tmp_path / "season_plan.xlsx"
        SeasonPlanExporter().export(sample_plan, str(output_path))

        workbook = openpyxl.load_workbook(str(output_path))
        overview = workbook["Sesongoversikt"]
        rows = list(overview.iter_rows(values_only=True))

        header, *data_rows = rows
        assert header == ("Dato", "Ukedag", "Aldersgruppe", "Arena", "Vertsklubb", "Lag")
        assert len(data_rows) == len(sample_plan.tournaments)

        for tournament, row in zip(sample_plan.tournaments, data_rows):
            expected_date = tournament.date.strftime("%d.%m.%Y")
            expected_weekday = _NORWEGIAN_WEEKDAYS[tournament.date.weekday()]
            expected_teams = ", ".join(team.label for team in tournament.teams)

            assert row[0] == expected_date
            assert row[1] == expected_weekday
            assert row[2] == tournament.age_group
            assert row[3] == tournament.arena
            assert row[4] == tournament.host_club
            assert row[5] == expected_teams

    def test_per_tournament_sheets_match_game_lists(self, sample_plan, tmp_path):
        output_path = tmp_path / "season_plan.xlsx"
        SeasonPlanExporter().export(sample_plan, str(output_path))

        workbook = openpyxl.load_workbook(str(output_path))

        for tournament in sample_plan.tournaments:
            # Find the sheet whose title contains this tournament's date prefix.
            date_prefix = tournament.date.strftime("%d.%m")
            matching_sheets = [
                workbook[name] for name in workbook.sheetnames
                if name.startswith(date_prefix) and tournament.age_group in name
            ]
            assert len(matching_sheets) == 1, f"expected exactly one sheet for {tournament.date} {tournament.age_group}"
            sheet = matching_sheets[0]

            rows = list(sheet.iter_rows(values_only=True))
            # Find the header row for the games table.
            header_index = next(
                i for i, row in enumerate(rows)
                if row[:4] == ("Kamp #", "Hjemmelag", "Bortelag", "Parallellbane")
            )
            game_rows = rows[header_index + 1:header_index + 1 + len(tournament.games)]

            assert len(game_rows) == len(tournament.games)
            for game_number, (game, row) in enumerate(zip(tournament.games, game_rows), start=1):
                assert row[0] == game_number
                assert row[1] == game.home.label
                assert row[2] == game.away.label
                assert row[3] == game.parallel_slot + 1  # exporter displays 1-based slots

    def test_sheet_titles_are_unique_and_within_excel_limits(self, sample_plan, tmp_path):
        output_path = tmp_path / "season_plan.xlsx"
        SeasonPlanExporter().export(sample_plan, str(output_path))

        workbook = openpyxl.load_workbook(str(output_path))
        titles = workbook.sheetnames

        assert len(titles) == len(set(titles)), "sheet titles must be unique"
        for title in titles:
            assert len(title) <= 31
