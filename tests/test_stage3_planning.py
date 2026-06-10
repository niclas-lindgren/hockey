"""Tests for tournament_scheduler.pipeline.stage3_planning."""

from datetime import date, datetime

from tournament_scheduler.models import Game, SeasonPlan, Team, Tournament
from tournament_scheduler.pipeline.stage3_planning import (
    Stage3Error,
    _plan_to_dict,
    run,
)
from tournament_scheduler.pipeline.state import PipelineState, StageName


def _make_config():
    clubs = [
        "Kongsberg", "Skien", "Ringerike", "Tønsberg",
        "Frisk Asker", "Sandefjord Penguins", "Jar",
    ]
    teams = [
        {"club": c, "label": f"{c} U10A", "age_group": "U10"}
        for c in clubs
    ]
    return {
        "start_date": "2025-09-01",
        "end_date": "2025-12-15",
        "age_groups": ["U10"],
        "parallel_games": {"U10": 2},
        "teams": teams,
    }


class TestRunStage3:
    def test_accepts_plan_without_llm(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        result = run(
            _make_config(), {},
            state,
            datetime(2025, 9, 1), datetime(2025, 12, 15),
        )
        assert state.is_done(StageName.PLANNING)
        assert "plan" in result
        assert len(result["plan"]["tournaments"]) > 0

    def test_plan_contains_expected_fields(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        result = run(
            _make_config(), {},
            state,
            datetime(2025, 9, 1), datetime(2025, 12, 15),
        )
        plan = result["plan"]
        assert "tournaments" in plan
        assert "diversity_score" in plan
        assert "month_balance_score" in plan

    def test_plan_accepted_without_llm_evaluation(self, tmp_path):
        """Plan is accepted deterministically without LLM evaluation."""
        state = PipelineState(tmp_path / "pipeline")
        result = run(
            _make_config(), {},
            state,
            datetime(2025, 9, 1), datetime(2025, 12, 15),
        )

        assert state.is_done(StageName.PLANNING)
        assert "plan" in result
        assert len(result["plan"]["tournaments"]) > 0
        # No LLM fields should be present (LLM eval was removed from Stage 3)
        assert "llm_confidence" not in result
        assert "llm_skipped" not in result




    def test_marks_checkpoint_done(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        run(
            _make_config(), {},
            state,
            datetime(2025, 9, 1), datetime(2025, 12, 15),
        )
        assert state.is_done(StageName.PLANNING)


class TestPlanToDict:
    def test_serializes_round_number(self):
        home = Team(club="Kongsberg", label="Kongsberg U10A", age_group="U10")
        away = Team(club="Skien", label="Skien U10A", age_group="U10")
        game = Game(home=home, away=away, parallel_slot=1, round_number=3)
        tournament = Tournament(
            date=date(2025, 10, 5),
            arena="Kongsberghallen",
            age_group="U10",
            teams=[home, away],
            games=[game],
        )
        plan = SeasonPlan(tournaments=[tournament])

        plan_dict = _plan_to_dict(plan)

        game_dict = plan_dict["tournaments"][0]["games"][0]
        assert game_dict["round_number"] == 3
