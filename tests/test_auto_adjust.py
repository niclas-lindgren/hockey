"""Unit tests for the auto-adjust loop and suggest_moves translator."""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from unittest.mock import MagicMock, call, patch

import pytest

from tournament_scheduler.cli.plan_critic import suggest_moves
from tournament_scheduler.models import SeasonPlan, Tournament


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tournament(
    host_club: str,
    year: int,
    month: int,
    day: int,
    age_group: str = "U10",
    arena: str | None = None,
) -> Tournament:
    return Tournament(
        date=date(year, month, day),
        arena=arena or f"{host_club} arena",
        age_group=age_group,
        host_club=host_club,
    )


def _make_plan(**kwargs) -> SeasonPlan:
    defaults: dict = {
        "tournaments": [],
        "team_game_counts": {},
        "game_count_spread": 0,
        "month_balance_score": 1.0,
        "fairness_gate": {},
        "arena_day_collisions": [],
    }
    defaults.update(kwargs)
    return SeasonPlan(**defaults)


def _auto_adjust_args(**kwargs) -> argparse.Namespace:
    defaults = dict(
        work_dir=".pipeline",
        export_dir="export",
        max_iterations=3,
        timestamped_export=False,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# suggest_moves — per issue category
# ---------------------------------------------------------------------------


class TestSuggestMovesArenaDayCollision:
    def test_auto_fixable_when_collision_data_exists(self):
        t = _make_tournament("ClubA", 2027, 3, 1, arena="Arena X")
        collision = {
            "date": "2027-03-01",
            "arena": "Arena X",
            "age_group": "U10",
            "host_club": "ClubA",
            "conflicting_age_group": "U12",
            "conflicting_host_club": "ClubB",
            "reason": "same_arena_same_day",
        }
        plan = _make_plan(
            tournaments=[t],
            arena_day_collisions=[collision],
        )
        issue = "1 arena-day collision(s) detected — review date assignments for arenas scheduled on the same day"
        moves = suggest_moves(plan, [issue])

        assert len(moves) == 1
        m = moves[0]
        assert m["can_auto_fix"] is True
        assert m["issue"] == issue
        assert m["tournament_id"] == t.id
        # new_date should be 7 days after collision date
        assert m["new_date"] == (date(2027, 3, 1) + timedelta(weeks=1)).isoformat()

    def test_not_auto_fixable_when_no_collision_data(self):
        plan = _make_plan(arena_day_collisions=[])
        issue = "2 arena-day collision(s) detected — review date assignments for arenas scheduled on the same day"
        moves = suggest_moves(plan, [issue])

        assert len(moves) == 1
        assert moves[0]["can_auto_fix"] is False
        assert moves[0]["tournament_id"] == ""

    def test_new_date_is_one_week_later(self):
        t = _make_tournament("ClubA", 2027, 12, 27, arena="IceArena")
        collision = {
            "date": "2027-12-27",
            "arena": "IceArena",
            "age_group": "U10",
            "host_club": "ClubA",
            "conflicting_age_group": "U8",
            "conflicting_host_club": "ClubC",
            "reason": "same_arena_same_day",
        }
        plan = _make_plan(tournaments=[t], arena_day_collisions=[collision])
        issue = "1 arena-day collision(s) detected — review date assignments for arenas scheduled on the same day"
        moves = suggest_moves(plan, [issue])

        assert moves[0]["new_date"] == "2028-01-03"


class TestSuggestMovesHostingClump:
    def test_auto_fixable_clump(self):
        t1 = _make_tournament("Kongsberg", 2027, 9, 4)
        t2 = _make_tournament("Kongsberg", 2027, 9, 11)
        t3 = _make_tournament("Kongsberg", 2027, 9, 18)
        plan = _make_plan(tournaments=[t1, t2, t3])
        issue = "Kongsberg hosts 3 tournaments in September 2027 — consider moving one to another club"
        moves = suggest_moves(plan, [issue])

        assert len(moves) == 1
        m = moves[0]
        assert m["can_auto_fix"] is True
        assert m["tournament_id"] == t3.id  # last in month
        expected_new_date = (date(2027, 9, 18) + timedelta(weeks=1)).isoformat()
        assert m["new_date"] == expected_new_date

    def test_clump_targets_last_tournament_in_month(self):
        t1 = _make_tournament("Ringerike", 2027, 10, 2)
        t2 = _make_tournament("Ringerike", 2027, 10, 9)
        t3 = _make_tournament("Ringerike", 2027, 10, 16)
        plan = _make_plan(tournaments=[t1, t2, t3])
        issue = "Ringerike hosts 3 tournaments in October 2027 — consider moving one to another club"
        moves = suggest_moves(plan, [issue])

        assert moves[0]["tournament_id"] == t3.id


class TestSuggestMovesFairnessGate:
    def test_fail_not_auto_fixable(self):
        issue = "Fairness gate FAIL: hosting_balance (value=0.3, threshold=0.6)"
        moves = suggest_moves(_make_plan(), [issue])

        assert len(moves) == 1
        assert moves[0]["can_auto_fix"] is False
        assert moves[0]["tournament_id"] == ""
        assert moves[0]["new_date"] is None

    def test_warning_not_auto_fixable(self):
        issue = "Fairness gate warning: diversity_score (value=0.55, threshold=0.6)"
        moves = suggest_moves(_make_plan(), [issue])

        assert len(moves) == 1
        assert moves[0]["can_auto_fix"] is False

    def test_fail_with_detail_not_auto_fixable(self):
        issue = "Fairness gate FAIL: hosting_balance — ClubA hosts 70% of tournaments"
        moves = suggest_moves(_make_plan(), [issue])

        assert moves[0]["can_auto_fix"] is False


class TestSuggestMovesGameCountSpread:
    def test_spread_not_auto_fixable(self):
        issue = "Game count spread 6: TeamA plays 12 games vs TeamB's 6 — redistribute game assignments"
        moves = suggest_moves(_make_plan(), [issue])

        assert len(moves) == 1
        assert moves[0]["can_auto_fix"] is False
        assert moves[0]["tournament_id"] == ""


class TestSuggestMovesMonthBalance:
    def test_low_balance_not_auto_fixable(self):
        issue = "Tournaments are unevenly spread across months (balance score=0.45) — consider redistributing"
        moves = suggest_moves(_make_plan(), [issue])

        assert len(moves) == 1
        assert moves[0]["can_auto_fix"] is False

    def test_balance_score_keyword_matches(self):
        issue = "balance score=0.3"
        moves = suggest_moves(_make_plan(), [issue])

        assert moves[0]["can_auto_fix"] is False


class TestSuggestMovesUnrecognised:
    def test_unrecognised_returns_non_auto_fixable(self):
        issue = "Some completely unknown issue string"
        moves = suggest_moves(_make_plan(), [issue])

        assert len(moves) == 1
        assert moves[0]["can_auto_fix"] is False
        assert moves[0]["issue"] == issue

    def test_multiple_issues_produce_multiple_moves(self):
        issues = [
            "Fairness gate FAIL: x (value=0, threshold=1)",
            "Game count spread 8: A plays 10 vs B's 2 — redistribute game assignments",
        ]
        moves = suggest_moves(_make_plan(), issues)

        assert len(moves) == 2
        assert all(not m["can_auto_fix"] for m in moves)


# ---------------------------------------------------------------------------
# _cmd_auto_adjust — loop behaviour
# ---------------------------------------------------------------------------


def _make_checkpoint(plan: SeasonPlan) -> dict:
    return {"plan": plan}


class TestCmdAutoAdjustLoopBehavior:
    """Tests for the iteration / early-exit / max-iterations behaviour."""

    def _patch_state(self, checkpoints: list):
        """Return a context manager that patches PipelineState.read_stage."""
        mock_state = MagicMock()
        mock_state.read_stage.side_effect = checkpoints
        return patch(
            "tournament_scheduler.cli.rvv_cli.PipelineState",
            return_value=mock_state,
        )

    def test_exits_early_when_no_issues(self):
        """Loop should exit after 0 iterations if the plan has no issues."""
        from tournament_scheduler.cli.rvv_cli import _cmd_auto_adjust

        clean_plan = _make_plan()
        checkpoint = _make_checkpoint(clean_plan)

        with patch(
            "tournament_scheduler.pipeline.state.PipelineState.read_stage",
            return_value=checkpoint,
        ), patch("tournament_scheduler.cli.rvv_cli._cmd_replan") as mock_replan:
            args = _auto_adjust_args(max_iterations=5)
            rc = _cmd_auto_adjust(args)

        assert rc == 0
        mock_replan.assert_not_called()

    def test_applies_move_and_reloads_checkpoint(self):
        """Loop should apply one auto-fixable move then reload the checkpoint."""
        from tournament_scheduler.cli.rvv_cli import _cmd_auto_adjust

        # First checkpoint: plan with a hosting clump (3 tournaments by ClubA in Jan 2027)
        t1 = _make_tournament("ClubA", 2027, 1, 8)
        t2 = _make_tournament("ClubA", 2027, 1, 15)
        t3 = _make_tournament("ClubA", 2027, 1, 22)
        clumped_plan = _make_plan(tournaments=[t1, t2, t3])

        # Second checkpoint (after replan): plan with no issues
        clean_plan = _make_plan()

        call_count = 0

        def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return _make_checkpoint(clumped_plan)
            return _make_checkpoint(clean_plan)

        with patch(
            "tournament_scheduler.pipeline.state.PipelineState.read_stage",
            side_effect=_side_effect,
        ), patch(
            "tournament_scheduler.cli.rvv_cli._cmd_replan", return_value=0
        ) as mock_replan:
            args = _auto_adjust_args(max_iterations=5)
            rc = _cmd_auto_adjust(args)

        assert rc == 0
        assert mock_replan.call_count >= 1

    def test_stops_at_max_iterations(self):
        """Loop should stop at max_iterations even when issues persist."""
        from tournament_scheduler.cli.rvv_cli import _cmd_auto_adjust

        # Plan always has a clump — replan never actually clears it in our mock
        t1 = _make_tournament("ClubX", 2027, 2, 5)
        t2 = _make_tournament("ClubX", 2027, 2, 12)
        t3 = _make_tournament("ClubX", 2027, 2, 19)
        persistent_plan = _make_plan(tournaments=[t1, t2, t3])

        with patch(
            "tournament_scheduler.pipeline.state.PipelineState.read_stage",
            return_value=_make_checkpoint(persistent_plan),
        ), patch(
            "tournament_scheduler.cli.rvv_cli._cmd_replan", return_value=0
        ) as mock_replan:
            args = _auto_adjust_args(max_iterations=2)
            rc = _cmd_auto_adjust(args)

        assert rc == 0
        # Should have attempted at most max_iterations moves
        assert mock_replan.call_count <= 2

    def test_escalates_when_only_manual_issues_remain(self):
        """When all remaining issues are non-auto-fixable, loop should stop and escalate."""
        from tournament_scheduler.cli.rvv_cli import _cmd_auto_adjust

        fairness_plan = _make_plan(
            fairness_gate={
                "status": "fail",
                "metrics": [
                    {
                        "status": "fail",
                        "label": "hosting_balance",
                        "value": 0.2,
                        "threshold": 0.6,
                        "detail": "",
                    }
                ],
            }
        )

        with patch(
            "tournament_scheduler.pipeline.state.PipelineState.read_stage",
            return_value=_make_checkpoint(fairness_plan),
        ), patch(
            "tournament_scheduler.cli.rvv_cli._cmd_replan"
        ) as mock_replan, patch(
            "tournament_scheduler.cli.rvv_cli._print_escalation_table"
        ) as mock_escalate:
            args = _auto_adjust_args(max_iterations=3)
            rc = _cmd_auto_adjust(args)

        assert rc == 0
        # Replan should never be called for non-auto-fixable issues
        mock_replan.assert_not_called()
        # Escalation table should be printed
        mock_escalate.assert_called_once()

    def test_missing_checkpoint_returns_1(self):
        """Missing checkpoint should return exit code 1."""
        from tournament_scheduler.cli.rvv_cli import _cmd_auto_adjust

        with patch(
            "tournament_scheduler.pipeline.state.PipelineState.read_stage",
            return_value=None,
        ):
            args = _auto_adjust_args()
            rc = _cmd_auto_adjust(args)

        assert rc == 1
