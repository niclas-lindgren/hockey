"""Unit tests for stage3_helpers._build_events_by_club logging."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tournament_scheduler.pipeline.stage3_helpers import _build_events_by_club


VALID_EVENT = {
    "date": "2025-11-01",
    "name": "Ishockey",
    "datetime": "2025-11-01T10:00:00",
    "duration_hours": 2.0,
}

MISSING_DATETIME_EVENT = {
    "date": "2025-11-02",
    "name": "Bad event",
    # "datetime" key intentionally omitted — will raise KeyError
}

BAD_DATETIME_EVENT = {
    "date": "2025-11-03",
    "name": "Also bad",
    "datetime": "not-a-valid-iso-string",  # will raise ValueError
}


class TestBuildEventsByClubLogging:
    """_build_events_by_club should log a warning for each malformed event."""

    def test_warning_emitted_for_missing_datetime_key(self) -> None:
        scraping_result = {
            "events_by_club": {
                "Kongsberg": [MISSING_DATETIME_EVENT],
            }
        }
        with patch(
            "tournament_scheduler.pipeline.stage3_helpers.logger"
        ) as mock_logger:
            _build_events_by_club(scraping_result)

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        # First positional arg is the format string; remaining args fill placeholders.
        assert "Kongsberg" in call_args.args

    def test_warning_emitted_for_bad_iso_string(self) -> None:
        scraping_result = {
            "events_by_club": {
                "Ringerike": [BAD_DATETIME_EVENT],
            }
        }
        with patch(
            "tournament_scheduler.pipeline.stage3_helpers.logger"
        ) as mock_logger:
            _build_events_by_club(scraping_result)

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert "Ringerike" in call_args.args

    def test_well_formed_events_still_returned(self) -> None:
        scraping_result = {
            "events_by_club": {
                "Skien": [VALID_EVENT],
            }
        }
        result = _build_events_by_club(scraping_result)

        assert "Skien" in result
        assert len(result["Skien"]) == 1
        assert result["Skien"][0].name == "Ishockey"

    def test_well_formed_events_returned_alongside_malformed(self) -> None:
        """Good events in the same club list must survive a bad neighbour."""
        scraping_result = {
            "events_by_club": {
                "Jutul": [MISSING_DATETIME_EVENT, VALID_EVENT],
            }
        }
        with patch(
            "tournament_scheduler.pipeline.stage3_helpers.logger"
        ) as mock_logger:
            result = _build_events_by_club(scraping_result)

        # One warning for the bad event.
        mock_logger.warning.assert_called_once()
        # Good event survives.
        assert len(result["Jutul"]) == 1
        assert result["Jutul"][0].name == "Ishockey"

    def test_warning_count_matches_malformed_event_count(self) -> None:
        scraping_result = {
            "events_by_club": {
                "Holmen": [
                    MISSING_DATETIME_EVENT,
                    BAD_DATETIME_EVENT,
                    VALID_EVENT,
                ],
            }
        }
        with patch(
            "tournament_scheduler.pipeline.stage3_helpers.logger"
        ) as mock_logger:
            result = _build_events_by_club(scraping_result)

        assert mock_logger.warning.call_count == 2
        assert len(result["Holmen"]) == 1

    def test_no_warnings_for_entirely_valid_input(self) -> None:
        scraping_result = {
            "events_by_club": {
                "Jar": [VALID_EVENT],
            }
        }
        with patch(
            "tournament_scheduler.pipeline.stage3_helpers.logger"
        ) as mock_logger:
            _build_events_by_club(scraping_result)

        mock_logger.warning.assert_not_called()

    def test_returns_empty_dict_for_none_input(self) -> None:
        result = _build_events_by_club(None)
        assert result == {}

    def test_returns_empty_dict_for_missing_events_by_club_key(self) -> None:
        result = _build_events_by_club({"other_key": "value"})
        assert result == {}
