from tournament_scheduler.fairness_model import FairnessModelConfig, SeasonFairnessModel
from tournament_scheduler.models import Roster, Team


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
