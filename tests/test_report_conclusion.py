"""Unit tests for tournament_scheduler.html.renderers.conclusion."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tournament_scheduler.html.renderers.conclusion import generate_report_conclusion
from tournament_scheduler.llm.lm_studio_client import LMStudioUnavailableError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_client(text: str) -> MagicMock:
    """Return a mock LMStudioClient whose complete() returns *text*."""
    mock = MagicMock()
    mock.complete.return_value.text = text
    return mock


def _make_plan(
    *,
    gate_status: str = "pass",
    gate_score: float = 0.85,
    pairwise: float | None = 0.9,
    diversity: float | None = 0.8,
    month_balance: float | None = 0.75,
    manual_adjustments: dict | None = None,
) -> object:
    """Return a minimal plan-like object."""

    class _Plan:
        fairness_gate = {"status": gate_status, "score": gate_score}
        pairwise_matchup_score = pairwise
        diversity_score = diversity
        month_balance_score = month_balance

    plan = _Plan()
    plan.manual_adjustments = manual_adjustments or {}
    return plan


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGenerateReportConclusion:
    """Tests for generate_report_conclusion()."""

    def test_returns_llm_text_when_client_available(self):
        """When the LLM client returns a non-empty string, function returns it."""
        client = _make_mock_client("Dette er en god plan.")
        plan = _make_plan()

        result = generate_report_conclusion(plan, blocked=None, client=client)

        assert result == "Dette er en god plan."

    def test_client_called_with_norwegian_system_prompt(self):
        """The system prompt must be in Norwegian."""
        client = _make_mock_client("OK")
        plan = _make_plan()

        generate_report_conclusion(plan, blocked=None, client=client)

        call_kwargs = client.complete.call_args
        system_prompt = call_kwargs.kwargs.get("system") or call_kwargs.args[0]
        assert "norsk" in system_prompt.lower() or "norwegian" in system_prompt.lower() or "norske" in system_prompt.lower()

    def test_returns_none_when_client_is_none(self):
        """When no client is provided, function returns None immediately."""
        plan = _make_plan()

        result = generate_report_conclusion(plan, blocked=None, client=None)

        assert result is None

    def test_returns_none_on_lm_studio_unavailable(self):
        """LMStudioUnavailableError must be caught and None returned."""
        client = MagicMock()
        client.complete.side_effect = LMStudioUnavailableError("server down")
        plan = _make_plan()

        result = generate_report_conclusion(plan, blocked=None, client=client)

        assert result is None

    def test_returns_none_when_llm_returns_empty_string(self):
        """An empty LLM response should be treated as unavailable."""
        client = _make_mock_client("")
        plan = _make_plan()

        result = generate_report_conclusion(plan, blocked=None, client=client)

        assert result is None

    def test_blocked_sources_included_in_user_prompt(self):
        """Blocked source names should appear in the user prompt sent to the LLM."""
        client = _make_mock_client("OK")
        plan = _make_plan()
        blocked = ["Ringerike", "Jarhallen"]

        generate_report_conclusion(plan, blocked=blocked, client=client)

        call_kwargs = client.complete.call_args
        user_prompt = call_kwargs.kwargs.get("user") or call_kwargs.args[1]
        assert "Ringerike" in user_prompt
        assert "Jarhallen" in user_prompt

    def test_no_blocked_sources_noted_when_empty(self):
        """When blocked is empty/None, prompt should say no blocked sources."""
        client = _make_mock_client("OK")
        plan = _make_plan()

        generate_report_conclusion(plan, blocked=[], client=client)

        call_kwargs = client.complete.call_args
        user_prompt = call_kwargs.kwargs.get("user") or call_kwargs.args[1]
        assert "ingen" in user_prompt.lower()

    def test_gate_status_in_user_prompt(self):
        """Gate status should appear in the user prompt."""
        client = _make_mock_client("OK")
        plan = _make_plan(gate_status="fail", gate_score=0.42)

        generate_report_conclusion(plan, blocked=None, client=client)

        call_kwargs = client.complete.call_args
        user_prompt = call_kwargs.kwargs.get("user") or call_kwargs.args[1]
        assert "fail" in user_prompt
        assert "0.42" in user_prompt

    def test_manual_adjustments_count_in_user_prompt(self):
        """When there are manual adjustments, count should appear in user prompt."""
        client = _make_mock_client("OK")
        plan = _make_plan(manual_adjustments={"U10": ["adj1", "adj2"], "U7": ["adj3"]})

        generate_report_conclusion(plan, blocked=None, client=client)

        call_kwargs = client.complete.call_args
        user_prompt = call_kwargs.kwargs.get("user") or call_kwargs.args[1]
        assert "3" in user_prompt  # 3 total adjustments

    def test_plan_with_no_metric_attributes(self):
        """Function should not raise when plan lacks optional score attributes."""

        class _MinimalPlan:
            fairness_gate = {"status": "pass", "score": 1.0}

        result = generate_report_conclusion(_MinimalPlan(), blocked=None, client=_make_mock_client("Fine."))

        assert result == "Fine."
