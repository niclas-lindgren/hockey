"""Tests for tournament_scheduler.pipeline.stage3_planning."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from tournament_scheduler.pipeline.stage3_planning import (
    MAX_RETRIES,
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
            llm_client=None,
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
            llm_client=None,
        )
        plan = result["plan"]
        assert "tournaments" in plan
        assert "diversity_score" in plan
        assert "month_balance_score" in plan

    def test_accepts_plan_with_high_confidence_llm(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")

        # Mock LLM returning high confidence
        mock_client = MagicMock()
        mock_client.complete.return_value = MagicMock(
            text='{"confidence": 0.9, "valid": true, "reasoning": "great plan"}'
        )

        result = run(
            _make_config(), {},
            state,
            datetime(2025, 9, 1), datetime(2025, 12, 15),
            llm_client=mock_client,
        )

        assert state.is_done(StageName.PLANNING)
        assert result["llm_confidence"] == pytest.approx(0.9)

    def test_retries_on_low_confidence(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")

        call_count = 0

        def fake_complete(system, user, temperature=0.2):
            nonlocal call_count
            call_count += 1
            # Low confidence for first two calls, high on third
            conf = 0.9 if call_count >= 3 else 0.3
            return MagicMock(
                text=f'{{"confidence": {conf}, "valid": true, "reasoning": "test"}}'
            )

        mock_client = MagicMock()
        mock_client.complete.side_effect = fake_complete

        result = run(
            _make_config(), {},
            state,
            datetime(2025, 9, 1), datetime(2025, 12, 15),
            llm_client=mock_client,
            max_retries=3,
        )

        # Should have retried and eventually accepted
        assert state.is_done(StageName.PLANNING)
        assert mock_client.complete.call_count >= 2

    def test_marks_checkpoint_done(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        run(
            _make_config(), {},
            state,
            datetime(2025, 9, 1), datetime(2025, 12, 15),
            llm_client=None,
        )
        assert state.is_done(StageName.PLANNING)
