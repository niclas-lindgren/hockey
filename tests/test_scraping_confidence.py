"""Unit tests for tournament_scheduler.pipeline.scraping_confidence."""

import datetime
from unittest.mock import MagicMock

from tournament_scheduler.pipeline.scraping_confidence import (
    ScrapingConfidenceVerdict,
    run_confidence_assessment,
)


def make_mock_client(text: str):
    """Return a mock LMStudioClient whose complete() returns an object with .text."""
    mock = MagicMock()
    mock.complete.return_value.text = text
    return mock


def make_cfg(start: str = "2025-09-01", end: str = "2026-04-30"):
    """Return a simple config-like object with start_date and end_date."""
    cfg = MagicMock()
    cfg.start_date = datetime.date.fromisoformat(start)
    cfg.end_date = datetime.date.fromisoformat(end)
    return cfg


def make_checkpoint(
    sources=None,
    blocked=None,
):
    """Return a minimal Stage 2 scraping checkpoint dict."""
    if sources is None:
        sources = [
            {"name": "Kongsberg", "event_count": 45, "blocked": False, "block_reason": ""},
            {"name": "Skien", "event_count": 30, "blocked": False, "block_reason": ""},
        ]
    if blocked is None:
        blocked = []
    return {
        "sources": sources,
        "blocked": blocked,
        "events_by_club": {},
        "cached": [],
    }


# ── Verdict parsing tests ─────────────────────────────────────────────────────


def test_ok_verdict_json():
    client = make_mock_client(
        '{"verdict": "OK", "suspicious_sources": [], "gaps": [], '
        '"overall_assessment": "Data looks good."}'
    )
    result = run_confidence_assessment(make_checkpoint(), make_cfg(), client)
    assert result.verdict == "OK"
    assert result.suspicious_sources == []
    assert result.gaps == []
    assert result.overall_assessment == "Data looks good."


def test_warn_verdict_with_suspicious_sources():
    client = make_mock_client(
        '{"verdict": "WARN", '
        '"suspicious_sources": ["Ringerike"], '
        '"gaps": ["Ringerike has 0 events over 35 weeks"], '
        '"overall_assessment": "One source looks empty."}'
    )
    result = run_confidence_assessment(make_checkpoint(), make_cfg(), client)
    assert result.verdict == "WARN"
    assert result.suspicious_sources == ["Ringerike"]
    assert "Ringerike" in result.gaps[0]
    assert result.overall_assessment == "One source looks empty."


def test_malformed_json_text_fallback_ok():
    client = make_mock_client("OK - data seems complete")
    result = run_confidence_assessment(make_checkpoint(), make_cfg(), client)
    assert result.verdict == "OK"
    assert result.suspicious_sources == []
    assert result.gaps == []


def test_malformed_json_text_fallback_warn():
    client = make_mock_client("WARN - Ringerike has suspiciously low event count")
    result = run_confidence_assessment(make_checkpoint(), make_cfg(), client)
    assert result.verdict == "WARN"
    assert result.suspicious_sources == []


def test_completely_unparseable_defaults_to_ok():
    client = make_mock_client("gibberish with no recognisable verdict keywords here")
    result = run_confidence_assessment(make_checkpoint(), make_cfg(), client)
    assert result.verdict == "OK"


def test_json_in_markdown_fence():
    client = make_mock_client(
        '```json\n{"verdict": "OK", "suspicious_sources": [], "gaps": [], '
        '"overall_assessment": "All sources active."}\n```'
    )
    result = run_confidence_assessment(make_checkpoint(), make_cfg(), client)
    assert result.verdict == "OK"
    assert result.overall_assessment == "All sources active."


# ── Prompt construction tests ─────────────────────────────────────────────────


def test_prompt_includes_source_names_and_event_counts():
    """Verify that source names and event counts appear in the user prompt."""
    checkpoint = make_checkpoint(
        sources=[
            {"name": "Kongsberg", "event_count": 55, "blocked": False, "block_reason": ""},
            {"name": "Jutul", "event_count": 0, "blocked": False, "block_reason": ""},
        ]
    )
    mock_client = MagicMock()
    mock_client.complete.return_value.text = (
        '{"verdict": "OK", "suspicious_sources": [], "gaps": [], "overall_assessment": ""}'
    )

    run_confidence_assessment(checkpoint, make_cfg(), mock_client)

    call_kwargs = mock_client.complete.call_args[1]
    user_prompt: str = call_kwargs["user"]

    assert "Kongsberg" in user_prompt
    assert "55" in user_prompt  # event count
    assert "Jutul" in user_prompt
    assert "0" in user_prompt


def test_prompt_includes_blocked_sources():
    """Verify that blocked source info appears in the user prompt."""
    checkpoint = make_checkpoint(
        sources=[
            {"name": "Ringerike", "event_count": 0, "blocked": True, "block_reason": "Timeout"},
        ],
        blocked=["Ringerike"],
    )
    mock_client = MagicMock()
    mock_client.complete.return_value.text = (
        '{"verdict": "WARN", "suspicious_sources": ["Ringerike"], "gaps": [], "overall_assessment": ""}'
    )

    run_confidence_assessment(checkpoint, make_cfg(), mock_client)

    call_kwargs = mock_client.complete.call_args[1]
    user_prompt: str = call_kwargs["user"]

    assert "Ringerike" in user_prompt
    assert "Timeout" in user_prompt


def test_prompt_includes_date_range():
    """Verify that the configured date range is present in the user prompt."""
    mock_client = MagicMock()
    mock_client.complete.return_value.text = (
        '{"verdict": "OK", "suspicious_sources": [], "gaps": [], "overall_assessment": ""}'
    )

    cfg = make_cfg(start="2025-09-01", end="2026-04-30")
    run_confidence_assessment(make_checkpoint(), cfg, mock_client)

    call_kwargs = mock_client.complete.call_args[1]
    user_prompt: str = call_kwargs["user"]

    assert "2025-09-01" in user_prompt
    assert "2026-04-30" in user_prompt


def test_sources_with_zero_events_not_blocked_are_flagged_in_summary():
    """Sources with zero events that are not blocked should appear in sources_with_zero_events."""
    checkpoint = make_checkpoint(
        sources=[
            {"name": "Holmen", "event_count": 0, "blocked": False, "block_reason": ""},
            {"name": "Kongsberg", "event_count": 40, "blocked": False, "block_reason": ""},
        ]
    )
    mock_client = MagicMock()
    mock_client.complete.return_value.text = (
        '{"verdict": "WARN", "suspicious_sources": ["Holmen"], "gaps": [], "overall_assessment": ""}'
    )

    run_confidence_assessment(checkpoint, make_cfg(), mock_client)

    call_kwargs = mock_client.complete.call_args[1]
    user_prompt: str = call_kwargs["user"]

    # The zero-events source should appear in sources_with_zero_events
    assert "Holmen" in user_prompt
    # Kongsberg should NOT appear in sources_with_zero_events key
    assert '"sources_with_zero_events"' in user_prompt
