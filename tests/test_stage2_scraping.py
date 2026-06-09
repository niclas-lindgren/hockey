"""Tests for tournament_scheduler.pipeline.stage2_scraping."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from tournament_scheduler.pipeline.stage2_scraping import (
    SOURCE_GOOGLE,
    SOURCE_ICAL,
    SOURCE_OUTLOOK,
    Stage2Error,
    _events_to_dicts,
    run,
)
from tournament_scheduler.pipeline.state import PipelineState, StageName
from tournament_scheduler.models import CalendarEvent


def _make_event(name: str = "Booking") -> CalendarEvent:
    return CalendarEvent(
        date="01.01.2025",
        name=name,
        datetime=datetime(2025, 1, 1, 10, 0),
        duration_hours=2.0,
    )


def _make_config_with_sources(sources):
    return {
        "start_date": "2025-09-01",
        "end_date": "2025-12-01",
        "teams": [],
        "sources": sources,
    }


class TestRunStage2:
    def test_empty_sources_produces_done_checkpoint(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        cfg = {"start_date": "2025-09-01", "end_date": "2025-12-01", "teams": []}
        result = run(
            cfg, state,
            datetime(2025, 9, 1), datetime(2025, 12, 1),
        )
        assert state.is_done(StageName.SCRAPING)
        assert result["sources"] == []

    def test_ical_source_has_no_llm_confidence(self, tmp_path):
        """iCal/Google sources do not get LLM confidence logged (informational)."""
        state = PipelineState(tmp_path / "pipeline")
        cfg = _make_config_with_sources([
            {"name": "Teamup", "type": SOURCE_ICAL, "url": "https://example.com/ical"},
        ])

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_ical_scraper",
            return_value=[_make_event()],
        ):
            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
            )

        # iCal sources should not have LLM confidence key
        src = result["sources"][0]
        assert "llm_confidence" not in src
        assert src["event_count"] == 1

    def test_zero_events_blocks_source(self, tmp_path):
        """A source returning zero events blocks the pipeline."""
        state = PipelineState(tmp_path / "pipeline")
        cfg = _make_config_with_sources([
            {"name": "HallX", "type": SOURCE_OUTLOOK, "url": "https://example.com"},
        ])

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_outlook_scraper",
            return_value=([], ""),
        ):
            with pytest.raises(Stage2Error) as exc_info:
                run(
                    cfg, state,
                    datetime(2025, 9, 1), datetime(2025, 12, 1),
                    strict=True,
                )
        assert "HallX" in str(exc_info.value)
        # No checkpoint file should be written when the pipeline blocks strictly
        assert not state.checkpoint_path(StageName.SCRAPING).exists()

    def test_zero_events_strict_false_does_not_raise(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        cfg = _make_config_with_sources([
            {"name": "HallY", "type": SOURCE_OUTLOOK, "url": "https://example.com"},
        ])

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_outlook_scraper",
            return_value=([], ""),
        ):
            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
                strict=False,
            )
        blocked = result.get("blocked", [])
        assert "HallY" in blocked

    def test_outlook_source_with_events_passes(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        cfg = _make_config_with_sources([
            {"name": "Kongsberg", "type": SOURCE_OUTLOOK, "url": "https://example.com"},
        ])
        events = [_make_event("Hockey practice")]

        with (
            patch(
                "tournament_scheduler.pipeline.stage2_scraping._run_outlook_scraper",
                return_value=(events, "<html/>"),
            ),
            patch("tournament_scheduler.pipeline.stage2_scraping._LLM_AVAILABLE", False),
        ):
            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
            )

        assert state.is_done(StageName.SCRAPING)
        src = result["sources"][0]
        assert src["event_count"] == 1
        assert src["blocked"] is False

    def test_outlook_source_llm_confidence_logged_when_available(self, tmp_path):
        """LLM confidence is logged for outlook sources when LM Studio is available."""
        state = PipelineState(tmp_path / "pipeline")
        cfg = _make_config_with_sources([
            {"name": "Kongsberg", "type": SOURCE_OUTLOOK, "url": "https://example.com"},
        ])
        events = [_make_event("Hockey practice")]

        with (
            patch(
                "tournament_scheduler.pipeline.stage2_scraping._run_outlook_scraper",
                return_value=(events, "<html/>"),
            ),
            patch("tournament_scheduler.pipeline.stage2_scraping._LLM_AVAILABLE", True),
            patch(
                "tournament_scheduler.pipeline.stage2_scraping._make_default_client",
            ) as mock_factory,
        ):
            mock_client = MagicMock()
            mock_client.complete.return_value = MagicMock(
                text='{"confidence": 0.8, "valid": true, "reasoning": "looks good"}'
            )
            mock_factory.return_value = mock_client

            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
            )

        src = result["sources"][0]
        assert src["llm_confidence"] == pytest.approx(0.8)
        assert src["event_count"] == 1


    def test_outlook_zero_events_with_html_fallback(self, tmp_path):
        """When scraper returns 0 events but raw HTML exists, LLM fallback is used."""
        state = PipelineState(tmp_path / "pipeline")
        cfg = _make_config_with_sources([
            {"name": "Kongsberg", "type": SOURCE_OUTLOOK, "url": "https://example.com"},
        ])
        raw = "<html>calendar content with events</html>"

        # Responses for the two LLM calls: first quality-gate (low conf),
        # second HTML fallback (extracted events).
        responses = [
            MagicMock(text='{"confidence": 0.2, "valid": false, "reasoning": "no events found by scraper"}'),  # quality gate
            MagicMock(text='[{"date": "01.01.2025", "name": "LLM-extracted", "duration_hours": 1.5}]'),  # html fallback
        ]

        with (
            patch(
                "tournament_scheduler.pipeline.stage2_scraping._run_outlook_scraper",
                return_value=([], raw),
            ),
            patch("tournament_scheduler.pipeline.stage2_scraping._LLM_AVAILABLE", True),
            patch(
                "tournament_scheduler.pipeline.stage2_scraping._make_default_client",
            ) as mock_factory,
        ):
            mock_client = MagicMock()
            mock_client.complete.side_effect = responses
            mock_factory.return_value = mock_client

            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
            )

        src = result["sources"][0]
        assert src["llm_fallback_used"] is True
        assert src["event_count"] == 1
        assert src["events"][0]["name"] == "LLM-extracted"
        assert src["blocked"] is False


class TestEventsToDict:
    def test_serialises_correctly(self):
        events = [_make_event("Practice")]
        dicts = _events_to_dicts(events)
        assert len(dicts) == 1
        assert dicts[0]["name"] == "Practice"
        assert dicts[0]["duration_hours"] == 2.0
        assert "datetime" in dicts[0]
