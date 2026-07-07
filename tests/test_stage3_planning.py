"""Tests for tournament_scheduler.pipeline.stage3_planning."""

from collections import Counter
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from tournament_scheduler.models import Game, SeasonPlan, Team, Tournament
from tournament_scheduler.pipeline.stage3_planning import (
    Stage3Error,
    _plan_to_dict,
    run,
)
from tournament_scheduler.pipeline.state import PipelineState, StageName, StageStatus
from tournament_scheduler.season_planner import _normalize_penalty_hints


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


def _make_duplicate_label_config():
    return {
        "start_date": "2025-09-01",
        "end_date": "2025-12-01",
        "age_groups": ["U10", "U11"],
        "parallel_games": {"U10": 2, "U11": 2},
        "fairness_thresholds": {
            "max_game_count_spread": 999,
            "max_hosting_deviation": 999,
            "max_team_travel_km": 9999,
            "min_diversity_score": 0.0,
            "min_pairwise_matchup_score": 0.0,
            "min_month_balance_score": 0.0,
            "max_same_weekend_club_load": 999,
            "max_consecutive_weekend_club_load": 999,
            "max_holiday_stretch_club_load": 999,
        },
        "teams": [
            {"club": "Jar", "label": "Jar 1 U10", "age_group": "U10"},
            {"club": "Kongsberg", "label": "Kongsberg 1 U10", "age_group": "U10"},
            {"club": "Ringerike", "label": "Ringerike 1 U10", "age_group": "U10"},
            {"club": "Jar", "label": "Jar 1 U11", "age_group": "U11"},
            {"club": "Kongsberg", "label": "Kongsberg 1 U11", "age_group": "U11"},
            {"club": "Ringerike", "label": "Ringerike 1 U11", "age_group": "U11"},
        ],
    }


class TestRunStage3:
    def test_season_planner_normalizes_structured_penalty_hints(self):
        assert _normalize_penalty_hints({
            "source": "mid_planning_critic",
            "penalty_hints": {"diversity_score": "70", "bad": "not-a-number"},
        }) == {"diversity_score": 70.0}

    def test_accepts_canonical_workbook_config(self, tmp_path, canonical_input_data, canonical_season_window):
        state = PipelineState(tmp_path / "pipeline")
        start, end = canonical_season_window
        result = run(canonical_input_data, {}, state, start, end)

        assert state.is_done(StageName.PLANNING)
        assert "plan" in result
        assert len(result["plan"]["tournaments"]) > 0

        configured_age_groups = set(canonical_input_data["age_groups"])
        planned_age_groups = {t["age_group"] for t in result["plan"]["tournaments"]}
        assert planned_age_groups <= configured_age_groups
        assert planned_age_groups

    def test_canonical_workbook_plan_covers_multiple_age_groups(self, tmp_path, canonical_input_data, canonical_season_window):
        state = PipelineState(tmp_path / "pipeline")
        start, end = canonical_season_window
        result = run(canonical_input_data, {}, state, start, end)

        counts = Counter(t["age_group"] for t in result["plan"]["tournaments"])
        assert len(counts) >= 3
        assert counts["U10"] > 0

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
        assert "arena_day_collisions" in plan

    def test_structured_planning_critic_hints_are_persisted_and_flattened(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        hints = {
            "source": "mid_planning_critic",
            "iteration": 1,
            "issues": ["game spread"],
            "penalty_hints": {"game_count_spread_score": "25", "ignored": "not-a-number"},
        }
        fake_planner = MagicMock()
        fake_planner.build_plan.return_value = SeasonPlan(
            tournaments=[
                Tournament(
                    date=date(2025, 10, 5),
                    arena="Kongsberghallen",
                    age_group="U10",
                    teams=[
                        Team(club="Kongsberg", label="Kongsberg U10A", age_group="U10"),
                        Team(club="Skien", label="Skien U10A", age_group="U10"),
                        Team(club="Jar", label="Jar U10A", age_group="U10"),
                    ],
                    games=[],
                )
            ]
        )
        fake_planner.rules_report.return_value = {"ok": True}
        cfg = {**_make_config(), "planning_critic_hints": hints}

        with patch("tournament_scheduler.pipeline.stage3_planning._make_planner", return_value=fake_planner) as make_planner, patch(
            "tournament_scheduler.pipeline.stage3_planning._build_fairness_gate",
            return_value={"score": 42},
        ):
            result = run(cfg, {}, state, datetime(2025, 9, 1), datetime(2025, 12, 15))

        assert result["planning_critic_hints"] == hints
        assert make_planner.call_args.kwargs["penalty_hints"] == {"game_count_spread_score": 25.0}

    def test_flat_penalty_hints_remain_supported(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        flat_hints = {"hosting_deviation_score": 30}
        fake_planner = MagicMock()
        fake_planner.build_plan.return_value = SeasonPlan(
            tournaments=[
                Tournament(
                    date=date(2025, 10, 5),
                    arena="Kongsberghallen",
                    age_group="U10",
                    teams=[
                        Team(club="Kongsberg", label="Kongsberg U10A", age_group="U10"),
                        Team(club="Skien", label="Skien U10A", age_group="U10"),
                        Team(club="Jar", label="Jar U10A", age_group="U10"),
                    ],
                    games=[],
                )
            ]
        )
        fake_planner.rules_report.return_value = {"ok": True}
        cfg = {**_make_config(), "penalty_hints": flat_hints}

        with patch("tournament_scheduler.pipeline.stage3_planning._make_planner", return_value=fake_planner) as make_planner, patch(
            "tournament_scheduler.pipeline.stage3_planning._build_fairness_gate",
            return_value={"score": 42},
        ):
            result = run(cfg, {}, state, datetime(2025, 9, 1), datetime(2025, 12, 15))

        assert result["planning_critic_hints"] == {
            "source": "penalty_hints",
            "penalty_hints": {"hosting_deviation_score": 30.0},
        }
        assert make_planner.call_args.kwargs["penalty_hints"] == {"hosting_deviation_score": 30.0}

    def test_workbook_level_planning_settings_are_passed_to_planner(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        fake_planner = MagicMock()
        fake_planner.build_plan.return_value = SeasonPlan(
            tournaments=[
                Tournament(
                    date=date(2025, 10, 5),
                    arena="Kongsberghallen",
                    age_group="U10",
                    teams=[
                        Team(club="Kongsberg", label="Kongsberg U10A", age_group="U10"),
                        Team(club="Skien", label="Skien U10A", age_group="U10"),
                        Team(club="Jar", label="Jar U10A", age_group="U10"),
                    ],
                    games=[],
                )
            ]
        )
        fake_planner.rules_report.return_value = {"ok": True}
        cfg = {
            **_make_config(),
            "target_tournament_count": 5,
            "max_hosting_days_per_month": 2,
        }

        with patch("tournament_scheduler.pipeline.stage3_planning._make_planner", return_value=fake_planner) as make_planner, patch(
            "tournament_scheduler.pipeline.stage3_planning._build_fairness_gate",
            return_value={"score": 42},
        ):
            run(cfg, {}, state, datetime(2025, 9, 1), datetime(2025, 12, 15))

        assert make_planner.call_args.args[7] == 5
        assert make_planner.call_args.kwargs["max_hosting_days_per_month"] == 2

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

    def test_emits_more_progress_after_optimization(self, tmp_path, capsys):
        state = PipelineState(tmp_path / "pipeline")
        run(
            _make_config(), {},
            state,
            datetime(2025, 9, 1), datetime(2025, 12, 15),
        )

        out = capsys.readouterr().out
        assert "[plan] Optimalisering: ferdig" in out
        assert "[plan] Optimalisering: starter reparasjonspassasje..." in out
        assert "[plan] Verter fordelt" in out

    def test_marks_checkpoint_done(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        run(
            _make_config(), {},
            state,
            datetime(2025, 9, 1), datetime(2025, 12, 15),
        )
        assert state.is_done(StageName.PLANNING)

    def test_preserves_manual_adjustments_from_previous_checkpoint(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        first = run(
            _make_config(), {},
            state,
            datetime(2025, 9, 1), datetime(2025, 12, 15),
        )
        checkpoint = dict(first)
        checkpoint["plan"] = dict(first["plan"])
        checkpoint["plan"]["manual_adjustments"] = {
            "locked_dates": ["2025-10-05"],
            "pinned_tournament_ids": ["abc12345"],
        }
        state.write_stage(StageName.PLANNING, checkpoint, status=StageStatus.DONE)

        second = run(
            _make_config(), {},
            state,
            datetime(2025, 9, 1), datetime(2025, 12, 15),
        )

        assert second["plan"]["manual_adjustments"]["locked_dates"] == ["2025-10-05"]
        assert second["plan"]["manual_adjustments"]["pinned_tournament_ids"] == ["abc12345"]

    def test_duplicate_labels_are_disambiguated_in_counts(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        result = run(
            _make_duplicate_label_config(), {},
            state,
            datetime(2025, 9, 1), datetime(2025, 12, 1),
        )
        plan = result["plan"]

        assert state.is_done(StageName.PLANNING)
        assert len(plan["team_game_counts"]) == 6
        assert any("U10" in key for key in plan["team_game_counts"])
        assert any("U11" in key for key in plan["team_game_counts"])
        assert plan["fairness_gate"]["status"] == "pass"


class TestIterationsFlag:
    """Tests for the --iterations multi-seed planning loop."""

    def test_iterations_one_produces_valid_plan(self, tmp_path):
        """iterations=1 (default) produces a non-empty plan, matching existing behavior."""
        state = PipelineState(tmp_path / "pipeline")
        result = run(
            _make_config(), {},
            state,
            datetime(2025, 9, 1), datetime(2025, 12, 15),
            iterations=1,
        )
        assert state.is_done(StageName.PLANNING)
        assert "plan" in result
        assert len(result["plan"]["tournaments"]) > 0

    def test_iterations_three_produces_valid_plan(self, tmp_path):
        """iterations=3 runs three seeds and keeps the best-scoring plan."""
        state = PipelineState(tmp_path / "pipeline")
        result = run(
            _make_config(), {},
            state,
            datetime(2025, 9, 1), datetime(2025, 12, 15),
            iterations=3,
        )
        assert state.is_done(StageName.PLANNING)
        assert "plan" in result
        assert len(result["plan"]["tournaments"]) > 0

    def test_multi_iteration_score_at_least_single_iteration(self, tmp_path):
        """The best plan from 3 iterations has a composite score >= the single-iteration plan."""
        cfg = _make_config()
        start = datetime(2025, 9, 1)
        end = datetime(2025, 12, 15)

        state_single = PipelineState(tmp_path / "single")
        result_single = run(cfg, {}, state_single, start, end, iterations=1)
        score_single = result_single["plan"].get("fairness_gate", {}).get("score", 0)

        state_multi = PipelineState(tmp_path / "multi")
        result_multi = run(cfg, {}, state_multi, start, end, iterations=3)
        score_multi = result_multi["plan"].get("fairness_gate", {}).get("score", 0)

        assert score_multi >= score_single


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
