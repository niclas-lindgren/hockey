"""Tests for tournament_scheduler.pipeline.stage1_config."""

import json
import tempfile
from pathlib import Path

import pytest

from tournament_scheduler.pipeline.stage1_config import (
    Stage1Error,
    run,
    validate_config,
)
from tournament_scheduler.pipeline.state import PipelineState, StageName, StageStatus


def _make_valid_raw():
    return {
        "start_date": "2025-09-01",
        "end_date": "2025-12-01",
        "teams": [
            {"club": "Kongsberg", "label": "Kongsberg U10A", "age_group": "U10"},
            {"club": "Skien",     "label": "Skien U10A",     "age_group": "U10"},
        ],
    }


class TestValidateConfig:
    def test_valid_config_has_no_errors(self):
        assert validate_config(_make_valid_raw()) == []

    def test_missing_start_date(self):
        raw = _make_valid_raw()
        del raw["start_date"]
        errors = validate_config(raw)
        assert any("start_date" in e for e in errors)

    def test_missing_end_date(self):
        raw = _make_valid_raw()
        del raw["end_date"]
        errors = validate_config(raw)
        assert any("end_date" in e for e in errors)

    def test_end_before_start_produces_error(self):
        raw = _make_valid_raw()
        raw["end_date"] = "2025-08-01"
        errors = validate_config(raw)
        assert any("end_date" in e for e in errors)

    def test_period_too_short(self):
        raw = _make_valid_raw()
        raw["start_date"] = "2025-09-01"
        raw["end_date"] = "2025-09-03"
        errors = validate_config(raw)
        assert any("dager" in e for e in errors)

    def test_invalid_date_format(self):
        raw = _make_valid_raw()
        raw["start_date"] = "01.09.2025"
        errors = validate_config(raw)
        assert any("ÅÅÅÅ-MM-DD" in e or "format" in e.lower() for e in errors)

    def test_missing_teams(self):
        raw = _make_valid_raw()
        del raw["teams"]
        errors = validate_config(raw)
        assert any("teams" in e for e in errors)

    def test_empty_teams_list(self):
        raw = _make_valid_raw()
        raw["teams"] = []
        errors = validate_config(raw)
        assert errors

    def test_unknown_age_group_in_team(self):
        raw = _make_valid_raw()
        raw["teams"][0]["age_group"] = "U99"
        errors = validate_config(raw)
        assert any("U99" in e for e in errors)

    def test_invalid_parallel_games_type(self):
        raw = _make_valid_raw()
        raw["parallel_games"] = "lots"
        errors = validate_config(raw)
        assert any("parallel_games" in e for e in errors)

    def test_parallel_games_exceed_federation_max(self):
        raw = _make_valid_raw()
        raw["parallel_games"] = {"U10": 999}
        errors = validate_config(raw)
        assert any("999" in e or "forbundets" in e for e in errors)

    def test_error_messages_are_norwegian(self):
        errors = validate_config({})
        # Norwegian error messages should contain Norwegian words
        combined = " ".join(errors)
        assert any(word in combined for word in ["Mangler", "felt", "Oppgi"])


class TestRunStage1:
    def test_run_writes_checkpoint_on_success(self, tmp_path):
        raw = _make_valid_raw()
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(raw))

        state = PipelineState(tmp_path / "pipeline")
        result = run(input_file, state)

        assert state.is_done(StageName.CONFIG)
        assert "teams" in result
        assert len(result["teams"]) == 2

    def test_run_raises_on_invalid_config(self, tmp_path):
        raw = {"start_date": "bad", "end_date": "also-bad", "teams": []}
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(raw))

        state = PipelineState(tmp_path / "pipeline")
        with pytest.raises(Stage1Error) as exc_info:
            run(input_file, state)
        assert len(exc_info.value.errors) > 0

    def test_run_raises_on_missing_field_no_checkpoint(self, tmp_path):
        raw = _make_valid_raw()
        del raw["start_date"]
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(raw))

        state = PipelineState(tmp_path / "pipeline")
        with pytest.raises(Stage1Error):
            run(input_file, state)
        assert not state.checkpoint_path(StageName.CONFIG).exists()

    def test_run_raises_on_missing_file(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        with pytest.raises(FileNotFoundError):
            run(tmp_path / "nonexistent.json", state)

    def test_run_strict_false_does_not_raise(self, tmp_path):
        raw = {}  # invalid but strict=False
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(raw))

        state = PipelineState(tmp_path / "pipeline")
        # Should not raise
        result = run(input_file, state, strict=False)
        # Result may be empty or partial
        assert isinstance(result, dict)
