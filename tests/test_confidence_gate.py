"""Unit tests for _run_confidence_gate in pipeline_orchestrator."""

from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from tournament_scheduler.cli.pipeline_orchestrator import _run_confidence_gate


def make_verdict(sources=None, gaps=None, assessment="low coverage"):
    """Return a mock ScrapingConfidenceVerdict."""
    v = MagicMock()
    v.overall_assessment = assessment
    v.suspicious_sources = sources or []
    v.gaps = gaps or []
    v.verdict = "WARN"
    return v


# ---------------------------------------------------------------------------
# Non-strict mode
# ---------------------------------------------------------------------------


def test_non_strict_returns_true_without_prompting():
    """In non-strict mode the gate must return True without calling input()."""
    console = Console(file=open("/dev/null", "w"))  # suppress output
    log_fn = MagicMock()
    verdict = make_verdict()

    with patch("builtins.input", side_effect=AssertionError("input must not be called in non-strict mode")):
        result = _run_confidence_gate(verdict, False, console, log_fn)

    assert result is True


def test_non_strict_calls_log_fn():
    """In non-strict mode the WARN details must be logged."""
    console = Console(file=open("/dev/null", "w"))
    log_fn = MagicMock()
    verdict = make_verdict(sources=["source_a"], assessment="sparse events")

    _run_confidence_gate(verdict, False, console, log_fn)

    log_fn.assert_called()
    # At least one call should mention WARN
    calls_text = " ".join(str(c) for c in log_fn.call_args_list)
    assert "WARN" in calls_text


# ---------------------------------------------------------------------------
# Strict mode — operator approves
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("answer", ["j", "y", "ja", "yes"])
def test_strict_operator_approves_returns_true(answer: str):
    """All accepted Norwegian/English approval answers must result in True."""
    console = Console(file=open("/dev/null", "w"))
    log_fn = MagicMock()
    verdict = make_verdict()

    with patch("builtins.input", return_value=answer):
        result = _run_confidence_gate(verdict, True, console, log_fn)

    assert result is True


# ---------------------------------------------------------------------------
# Strict mode — operator declines
# ---------------------------------------------------------------------------


def test_strict_operator_declines_returns_false():
    """'n' answer in strict mode must return False."""
    console = Console(file=open("/dev/null", "w"))
    log_fn = MagicMock()
    verdict = make_verdict()

    with patch("builtins.input", return_value="n"):
        result = _run_confidence_gate(verdict, True, console, log_fn)

    assert result is False


def test_strict_empty_answer_returns_false():
    """An empty answer in strict mode must return False."""
    console = Console(file=open("/dev/null", "w"))
    log_fn = MagicMock()
    verdict = make_verdict()

    with patch("builtins.input", return_value=""):
        result = _run_confidence_gate(verdict, True, console, log_fn)

    assert result is False


# ---------------------------------------------------------------------------
# Strict mode — input() raises
# ---------------------------------------------------------------------------


def test_strict_eof_returns_false():
    """EOFError from input() in strict mode must be treated as 'n'."""
    console = Console(file=open("/dev/null", "w"))
    log_fn = MagicMock()
    verdict = make_verdict()

    with patch("builtins.input", side_effect=EOFError):
        result = _run_confidence_gate(verdict, True, console, log_fn)

    assert result is False


def test_strict_keyboard_interrupt_returns_false():
    """KeyboardInterrupt from input() in strict mode must be treated as 'n'."""
    console = Console(file=open("/dev/null", "w"))
    log_fn = MagicMock()
    verdict = make_verdict()

    with patch("builtins.input", side_effect=KeyboardInterrupt):
        result = _run_confidence_gate(verdict, True, console, log_fn)

    assert result is False
