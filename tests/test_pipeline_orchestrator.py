"""Tests for _compute_verdict_tone and _run_refinement_loop in pipeline_orchestrator.py."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from tournament_scheduler.cli.pipeline_orchestrator import (
    _MAX_REFINEMENT_ITERATIONS,
    _compute_verdict_tone,
    _run_refinement_loop,
)
from tournament_scheduler.models import SeasonPlan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_plan_obj(
    *,
    gate_status: str = "pass",
    gate_score: int = 100,
    pairwise: float = 1.0,
    diversity: float = 1.0,
    month_balance: float = 1.0,
) -> SeasonPlan:
    plan = SeasonPlan(
        fairness_gate={"status": gate_status, "score": gate_score},
        pairwise_matchup_score=pairwise,
        diversity_score=diversity,
        month_balance_score=month_balance,
    )
    return plan


def _make_checkpoint(plan_obj: SeasonPlan) -> dict[str, Any]:
    return {"plan": plan_obj, "warnings": []}


def _make_state() -> MagicMock:
    state = MagicMock()
    state.read_stage.return_value = {"plan": MagicMock(spec=SeasonPlan)}
    return state


def _make_args() -> MagicMock:
    args = MagicMock()
    args.work_dir = "/tmp/test"
    args.export_dir = "export"
    args.timestamped_export = False
    return args


# ---------------------------------------------------------------------------
# _compute_verdict_tone — unit tests
# ---------------------------------------------------------------------------


class TestComputeVerdictTone:
    def test_strong_when_all_scores_perfect(self) -> None:
        plan = _make_plan_obj(gate_status="pass", gate_score=100, pairwise=1.0, diversity=1.0, month_balance=1.0)
        assert _compute_verdict_tone(plan) == "strong"

    def test_rough_when_gate_fails(self) -> None:
        plan = _make_plan_obj(gate_status="fail", gate_score=40, pairwise=0.5, diversity=0.5, month_balance=0.5)
        assert _compute_verdict_tone(plan) == "rough"

    def test_rough_when_gate_score_below_70(self) -> None:
        plan = _make_plan_obj(gate_status="pass", gate_score=65, pairwise=0.8, diversity=0.95, month_balance=0.95)
        assert _compute_verdict_tone(plan) == "rough"

    def test_rough_when_pairwise_below_0_75(self) -> None:
        plan = _make_plan_obj(gate_status="pass", gate_score=80, pairwise=0.7, diversity=0.95, month_balance=0.95)
        assert _compute_verdict_tone(plan) == "rough"

    def test_mixed_when_gate_warns(self) -> None:
        plan = _make_plan_obj(gate_status="warn", gate_score=85, pairwise=0.92, diversity=0.95, month_balance=0.95)
        assert _compute_verdict_tone(plan) == "mixed"

    def test_mixed_when_pairwise_between_75_and_90(self) -> None:
        plan = _make_plan_obj(gate_status="pass", gate_score=90, pairwise=0.80, diversity=0.95, month_balance=0.95)
        assert _compute_verdict_tone(plan) == "mixed"

    def test_mixed_when_diversity_below_0_9(self) -> None:
        plan = _make_plan_obj(gate_status="pass", gate_score=90, pairwise=0.92, diversity=0.85, month_balance=0.95)
        assert _compute_verdict_tone(plan) == "mixed"

    def test_mixed_when_month_balance_below_0_9(self) -> None:
        plan = _make_plan_obj(gate_status="pass", gate_score=90, pairwise=0.92, diversity=0.95, month_balance=0.85)
        assert _compute_verdict_tone(plan) == "mixed"

    def test_accepts_checkpoint_dict(self) -> None:
        plan_obj = _make_plan_obj(gate_status="pass", gate_score=95, pairwise=0.95, diversity=0.95, month_balance=0.95)
        checkpoint = _make_checkpoint(plan_obj)
        assert _compute_verdict_tone(checkpoint) == "strong"

    def test_accepts_bare_dict_without_plan_key(self) -> None:
        # A bare dict with no "plan" key should not crash
        result = _compute_verdict_tone({"pairwise_matchup_score": 0.5})
        # dict has no SeasonPlan attributes — defaults to 0s, gate_status=pass → rough
        assert result in ("rough", "mixed", "strong")

    def test_gate_status_case_insensitive(self) -> None:
        plan = _make_plan_obj(gate_status="FAIL", gate_score=40, pairwise=0.5, diversity=0.5, month_balance=0.5)
        assert _compute_verdict_tone(plan) == "rough"


# ---------------------------------------------------------------------------
# _run_refinement_loop — unit tests
# ---------------------------------------------------------------------------


def _make_update_result(*, success: bool = True) -> MagicMock:
    result = MagicMock()
    result.success = success
    result.summary_nb = "Ingen manuelle justeringer var nødvendige."
    return result


class TestRunRefinementLoop:
    """Tests for the skill-driven plan refinement loop."""

    def _patch_refinement(
        self,
        *,
        initial_tone: str = "rough",
        tone_after_apply: str = "mixed",
        critic_issues: list[str] | None = None,
        moves: list[dict] | None = None,
    ):
        """Return a context that patches all external dependencies of _run_refinement_loop."""
        if critic_issues is None:
            critic_issues = ["some issue"]
        if moves is None:
            moves = [{"tournament_id": "t1", "new_date": "2026-03-01", "reason": "test", "can_auto_fix": True, "issue": "some issue"}]

        plan_obj = _make_plan_obj(gate_status="pass", gate_score=95, pairwise=0.95, diversity=0.95, month_balance=0.95)

        return (plan_obj, [
            patch(
                "tournament_scheduler.cli.pipeline_orchestrator._compute_verdict_tone",
                side_effect=[initial_tone, tone_after_apply],
            ),
            patch(
                "tournament_scheduler.pipeline.manual_adjustment_workflow.ManualAdjustmentWorkflow.load_plan",
                return_value=plan_obj,
            ),
            patch(
                "tournament_scheduler.cli.plan_critic.generate_critic_summary",
                return_value=critic_issues,
            ),
            patch(
                "tournament_scheduler.cli.plan_critic.suggest_moves",
                return_value=moves,
            ),
            patch(
                "tournament_scheduler.pipeline.manual_adjustment_workflow.ManualAdjustmentWorkflow.apply",
                return_value=_make_update_result(success=True),
            ),
            patch(
                "tournament_scheduler.pipeline.tournament_updater.TournamentUpdater.write_updated_checkpoint",
            ),
        ])

    def test_exits_early_when_tone_not_rough(self) -> None:
        """If initial tone is already 'mixed', loop should return immediately without applying anything."""
        plan_obj = _make_plan_obj(gate_status="pass", gate_score=95, pairwise=0.95, diversity=0.95, month_balance=0.95)
        checkpoint = _make_checkpoint(plan_obj)
        state = _make_state()
        args = _make_args()
        log_calls: list[str] = []

        with patch(
            "tournament_scheduler.cli.pipeline_orchestrator._compute_verdict_tone",
            return_value="mixed",
        ) as mock_tone:
            tone, updated = _run_refinement_loop(checkpoint, state, args, False, log_calls.append)

        assert tone == "mixed"
        assert updated is checkpoint
        # _compute_verdict_tone called once for the check, then loop exits
        assert mock_tone.call_count == 1

    def test_exits_after_tone_improves_on_iteration_2(self) -> None:
        """Loop exits after tone becomes 'mixed' on the second iteration."""
        plan_obj = _make_plan_obj(gate_status="fail", gate_score=40, pairwise=0.5, diversity=0.5, month_balance=0.5)
        checkpoint = _make_checkpoint(plan_obj)
        state = _make_state()
        state.read_stage.return_value = checkpoint
        args = _make_args()
        log_calls: list[str] = []

        apply_result = _make_update_result(success=True)

        # First call: rough, second call: mixed → should exit after iteration 1 apply
        tone_sequence = ["rough", "mixed"]
        tone_iter = iter(tone_sequence)

        with patch(
            "tournament_scheduler.cli.pipeline_orchestrator._compute_verdict_tone",
            side_effect=tone_iter,
        ):
            with patch(
                "tournament_scheduler.pipeline.manual_adjustment_workflow.ManualAdjustmentWorkflow.load_plan",
                return_value=plan_obj,
            ):
                with patch(
                    "tournament_scheduler.cli.plan_critic.generate_critic_summary",
                    return_value=["Arena-day collision on 2026-03-01"],
                ):
                    with patch(
                        "tournament_scheduler.cli.plan_critic.suggest_moves",
                        return_value=[{
                            "tournament_id": "t1",
                            "new_date": "2026-03-08",
                            "reason": "shift",
                            "can_auto_fix": True,
                            "issue": "Arena-day collision on 2026-03-01",
                        }],
                    ):
                        with patch(
                            "tournament_scheduler.pipeline.manual_adjustment_workflow.ManualAdjustmentWorkflow.apply",
                            return_value=apply_result,
                        ):
                            with patch(
                                "tournament_scheduler.pipeline.tournament_updater.TournamentUpdater.write_updated_checkpoint",
                            ):
                                tone, updated = _run_refinement_loop(
                                    checkpoint, state, args, False, log_calls.append
                                )

        # After first iteration apply, tone becomes mixed → early exit before second iteration starts
        assert tone == "mixed"

    def test_exits_after_max_iterations_when_tone_stays_rough(self) -> None:
        """Loop stops after _MAX_REFINEMENT_ITERATIONS if tone never improves."""
        plan_obj = _make_plan_obj(gate_status="fail", gate_score=40, pairwise=0.5, diversity=0.5, month_balance=0.5)
        checkpoint = _make_checkpoint(plan_obj)
        state = _make_state()
        state.read_stage.return_value = checkpoint
        args = _make_args()
        log_calls: list[str] = []

        apply_result = _make_update_result(success=True)
        apply_mock = MagicMock(return_value=apply_result)

        # Always return 'rough' so the loop runs to the cap
        tone_values = ["rough"] * (_MAX_REFINEMENT_ITERATIONS + 1)

        with patch(
            "tournament_scheduler.cli.pipeline_orchestrator._compute_verdict_tone",
            side_effect=tone_values,
        ):
            with patch(
                "tournament_scheduler.pipeline.manual_adjustment_workflow.ManualAdjustmentWorkflow.load_plan",
                return_value=plan_obj,
            ):
                with patch(
                    "tournament_scheduler.cli.plan_critic.generate_critic_summary",
                    return_value=["some issue"],
                ):
                    with patch(
                        "tournament_scheduler.cli.plan_critic.suggest_moves",
                        return_value=[{
                            "tournament_id": "t1",
                            "new_date": "2026-03-08",
                            "reason": "shift",
                            "can_auto_fix": True,
                            "issue": "some issue",
                        }],
                    ):
                        with patch(
                            "tournament_scheduler.pipeline.manual_adjustment_workflow.ManualAdjustmentWorkflow.apply",
                            apply_mock,
                        ):
                            with patch(
                                "tournament_scheduler.pipeline.tournament_updater.TournamentUpdater.write_updated_checkpoint",
                            ):
                                tone, updated = _run_refinement_loop(
                                    checkpoint, state, args, False, log_calls.append
                                )

        # apply() called exactly _MAX_REFINEMENT_ITERATIONS times
        assert apply_mock.call_count == _MAX_REFINEMENT_ITERATIONS
        # Final tone is still rough
        assert tone == "rough"

    def test_stops_when_no_auto_fixable_moves(self) -> None:
        """Loop exits early when suggest_moves returns no auto-fixable entries."""
        plan_obj = _make_plan_obj(gate_status="fail", gate_score=40, pairwise=0.5, diversity=0.5, month_balance=0.5)
        checkpoint = _make_checkpoint(plan_obj)
        state = _make_state()
        args = _make_args()
        log_calls: list[str] = []

        apply_mock = MagicMock()

        with patch(
            "tournament_scheduler.cli.pipeline_orchestrator._compute_verdict_tone",
            return_value="rough",
        ):
            with patch(
                "tournament_scheduler.pipeline.manual_adjustment_workflow.ManualAdjustmentWorkflow.load_plan",
                return_value=plan_obj,
            ):
                with patch(
                    "tournament_scheduler.cli.plan_critic.generate_critic_summary",
                    return_value=["Fairness gate FAIL: some metric"],
                ):
                    with patch(
                        "tournament_scheduler.cli.plan_critic.suggest_moves",
                        return_value=[{
                            "tournament_id": "",
                            "new_date": None,
                            "reason": "needs human input",
                            "can_auto_fix": False,
                            "issue": "Fairness gate FAIL: some metric",
                        }],
                    ):
                        with patch(
                            "tournament_scheduler.pipeline.manual_adjustment_workflow.ManualAdjustmentWorkflow.apply",
                            apply_mock,
                        ):
                            tone, _ = _run_refinement_loop(
                                checkpoint, state, args, False, log_calls.append
                            )

        # apply() should NOT be called — no auto-fixable moves
        apply_mock.assert_not_called()

    def test_stops_when_no_critic_issues(self) -> None:
        """Loop exits early when generate_critic_summary returns an empty list."""
        plan_obj = _make_plan_obj(gate_status="fail", gate_score=40, pairwise=0.5, diversity=0.5, month_balance=0.5)
        checkpoint = _make_checkpoint(plan_obj)
        state = _make_state()
        args = _make_args()
        log_calls: list[str] = []

        apply_mock = MagicMock()

        with patch(
            "tournament_scheduler.cli.pipeline_orchestrator._compute_verdict_tone",
            return_value="rough",
        ):
            with patch(
                "tournament_scheduler.pipeline.manual_adjustment_workflow.ManualAdjustmentWorkflow.load_plan",
                return_value=plan_obj,
            ):
                with patch(
                    "tournament_scheduler.cli.plan_critic.generate_critic_summary",
                    return_value=[],
                ):
                    with patch(
                        "tournament_scheduler.pipeline.manual_adjustment_workflow.ManualAdjustmentWorkflow.apply",
                        apply_mock,
                    ):
                        tone, _ = _run_refinement_loop(
                            checkpoint, state, args, False, log_calls.append
                        )

        apply_mock.assert_not_called()
