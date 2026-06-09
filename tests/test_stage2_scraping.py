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

    def test_ical_source_skips_llm(self, tmp_path):
        """iCal/Google sources must NOT call the LLM client."""
        state = PipelineState(tmp_path / "pipeline")
        cfg = _make_config_with_sources([
            {"name": "Teamup", "type": SOURCE_ICAL, "url": "https://example.com/ical"},
        ])
        mock_client = MagicMock()

        # Patch the ical scraper to return events without network
        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_ical_scraper",
            return_value=[_make_event()],
        ):
            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
                llm_client=mock_client,
            )

        # LLM should never be called for iCal sources
        mock_client.complete.assert_not_called()
        assert len(result["sources"]) == 1
        assert result["sources"][0]["llm_skipped"] is True

    def test_zero_events_blocks_source(self, tmp_path):
        """A source returning zero events after both scraper and LLM fallback blocks the pipeline."""
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
                    llm_client=None,
                    strict=True,
                )
        assert "HallX" in str(exc_info.value)

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
                llm_client=None,
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

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_outlook_scraper",
            return_value=(events, "<html/>"),
        ):
            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
                llm_client=None,
            )

        assert state.is_done(StageName.SCRAPING)
        src = result["sources"][0]
        assert src["event_count"] == 1
        assert src["blocked"] is False


class TestEventsToDict:
    def test_serialises_correctly(self):
        events = [_make_event("Practice")]
        dicts = _events_to_dicts(events)
        assert len(dicts) == 1
        assert dicts[0]["name"] == "Practice"
        assert dicts[0]["duration_hours"] == 2.0
        assert "datetime" in dicts[0]
