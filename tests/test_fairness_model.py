from datetime import date

from tournament_scheduler.fairness_model import FairnessModelConfig, SeasonFairnessModel
from tournament_scheduler.models import Game, Roster, SeasonPlan, Team, Tournament


class TestSeasonFairnessModel:
    def test_larger_club_gets_higher_soft_target_than_single_team_club(self):
        roster = Roster(
            teams=[
                Team(club="Jar", label="Jar 1", age_group="U10"),
                Team(club="Jar", label="Jar 2", age_group="U10"),
                Team(club="Jar", label="Jar 3", age_group="U10"),
                Team(club="Kongsberg", label="Kongsberg 1", age_group="U10"),
            ]
        )
        team_game_counts = {
            "Jar 1": 18,
            "Jar 2": 19,
            "Jar 3": 20,
            "Kongsberg 1": 18,
        }

        model = SeasonFairnessModel(FairnessModelConfig(club_share_weight=0.5, max_adjustment=10))
        jar_target = model.target_games_for_team(roster.teams[0], roster.teams, team_game_counts)
        kongsberg_target = model.target_games_for_team(roster.teams[3], roster.teams, team_game_counts)

        assert jar_target > kongsberg_target
        assert jar_target == model.targets_for_age_group(roster.teams, team_game_counts)["Jar 1"]

    def test_empty_age_group_returns_zero_targets(self):
        model = SeasonFairnessModel()
        assert model.target_games_for_team(Team(club="Jar", label="Jar 1", age_group="U10"), [], {}) == 0.0

    def test_planning_target_seeds_empty_groups_with_a_non_zero_prior(self):
        teams = [
            Team(club="Jar", label="Jar 1", age_group="U10"),
            Team(club="Jar", label="Jar 2", age_group="U10"),
            Team(club="Kongsberg", label="Kongsberg 1", age_group="U10"),
        ]
        model = SeasonFairnessModel(FairnessModelConfig(club_share_weight=0.5, max_adjustment=10))

        jar_target = model.planning_target_games_for_team(teams[0], teams, {})
        kongsberg_target = model.planning_target_games_for_team(teams[2], teams, {})

        assert jar_target > kongsberg_target
        assert jar_target > 0
        assert kongsberg_target > 0

    def test_adjustment_rows_are_sorted_by_largest_gap_first(self):
        teams = [
            Team(club="Jar", label="Jar 1", age_group="U10"),
            Team(club="Jar", label="Jar 2", age_group="U10"),
            Team(club="Kongsberg", label="Kongsberg 1", age_group="U10"),
        ]
        tournament = Tournament(
            date=date(2026, 10, 10),
            arena="Jarhallen",
            age_group="U10",
            teams=teams,
            games=[Game(home=teams[0], away=teams[2]), Game(home=teams[1], away=teams[2])],
            host_club="Jar",
        )
        plan = SeasonPlan(
            tournaments=[tournament],
            team_game_counts={"Jar 1": 1, "Jar 2": 1, "Kongsberg 1": 2},
        )

        model = SeasonFairnessModel(FairnessModelConfig(club_share_weight=0.5, max_adjustment=10))
        rows = model.adjustment_rows_for_plan(plan)

        assert {row["label"] for row in rows} == {"Jar 1", "Jar 2", "Kongsberg 1"}
        assert abs(float(rows[0]["adjustment"])) >= abs(float(rows[1]["adjustment"])) >= abs(float(rows[2]["adjustment"]))
