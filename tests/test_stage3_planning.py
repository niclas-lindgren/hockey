"""Tests for tournament_scheduler.pipeline.stage3_planning."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from tournament_scheduler.pipeline.stage3_planning import (
    Stage3Error,
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

    @patch("tournament_scheduler.pipeline.stage3_planning._LLM_AVAILABLE", True)
    @patch(
        "tournament_scheduler.pipeline.stage3_planning._make_default_client",
    )
    def test_llm_confidence_logged_when_available(self, mock_factory, tmp_path):
        """LLM evaluation logs confidence but does NOT gate acceptance."""
        mock_client = MagicMock()
        mock_client.complete.return_value = MagicMock(
            text='{"confidence": 0.9, "valid": true, "reasoning": "great plan"}'
        )
        mock_factory.return_value = mock_client

        state = PipelineState(tmp_path / "pipeline")
        result = run(
            _make_config(), {},
            state,
            datetime(2025, 9, 1), datetime(2025, 12, 15),
        )

        assert state.is_done(StageName.PLANNING)
        assert result["llm_confidence"] == pytest.approx(0.9)
        assert result["llm_skipped"] is False

    @patch("tournament_scheduler.pipeline.stage3_planning._LLM_AVAILABLE", True)
    @patch(
        "tournament_scheduler.pipeline.stage3_planning._make_default_client",
    )
    def test_low_confidence_does_not_reject_plan(self, mock_factory, tmp_path):
        """LLM confidence is informational only — low score never rejects plan."""
        mock_client = MagicMock()
        mock_client.complete.return_value = MagicMock(
            text='{"confidence": 0.1, "valid": false, "reasoning": "looks wrong"}'
        )
        mock_factory.return_value = mock_client

        state = PipelineState(tmp_path / "pipeline")
        result = run(
            _make_config(), {},
            state,
            datetime(2025, 9, 1), datetime(2025, 12, 15),
        )

        # Plan is accepted regardless of low LLM confidence
        assert state.is_done(StageName.PLANNING)
        assert "plan" in result
        assert len(result["plan"]["tournaments"]) > 0
        assert result["llm_confidence"] == pytest.approx(0.1)

    @patch("tournament_scheduler.pipeline.stage3_planning._LLM_AVAILABLE", True)
    @patch(
        "tournament_scheduler.pipeline.stage3_planning._make_default_client",
    )
    def test_llm_offline_skips_gate(self, mock_factory, tmp_path):
        """When LM Studio is unreachable, skip LLM gate without error."""
        from tournament_scheduler.llm.lm_studio_client import (
            LMStudioUnavailableError,
        )

        mock_factory.side_effect = LMStudioUnavailableError("offline")

        state = PipelineState(tmp_path / "pipeline")
        result = run(
            _make_config(), {},
            state,
            datetime(2025, 9, 1), datetime(2025, 12, 15),
        )

        assert state.is_done(StageName.PLANNING)
        assert result["llm_skipped"] is True
        assert result["llm_confidence"] == 0.0

    def test_marks_checkpoint_done(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        run(
            _make_config(), {},
            state,
            datetime(2025, 9, 1), datetime(2025, 12, 15),
        )
        assert state.is_done(StageName.PLANNING)
