"""Tests for tournament_scheduler.pipeline.state (PipelineState)."""

import json
import tempfile
from pathlib import Path

import pytest

from tournament_scheduler.pipeline.state import (
    PipelineState,
    StageName,
    StageStatus,
)


@pytest.fixture()
def tmp_state(tmp_path):
    return PipelineState(tmp_path / "pipeline")


class TestPipelineState:
    def test_creates_work_dir(self, tmp_path):
        work_dir = tmp_path / "newdir"
        assert not work_dir.exists()
        PipelineState(work_dir)
        assert work_dir.exists()

    def test_write_and_read_stage(self, tmp_state):
        data = {"teams": ["A", "B"], "start_date": "2025-09-01"}
        tmp_state.write_stage(StageName.CONFIG, data)
        assert tmp_state.read_stage(StageName.CONFIG) == data

    def test_initial_status_is_pending(self, tmp_state):
        assert tmp_state.status(StageName.CONFIG) == StageStatus.PENDING

    def test_mark_done(self, tmp_state):
        tmp_state.write_stage(StageName.CONFIG, {})
        tmp_state.mark_done(StageName.CONFIG)
        assert tmp_state.is_done(StageName.CONFIG)

    def test_mark_failed(self, tmp_state):
        tmp_state.write_stage(StageName.CONFIG, {})
        tmp_state.mark_failed(StageName.CONFIG, error="something broke")
        assert tmp_state.is_failed(StageName.CONFIG)

    def test_read_envelope_contains_status(self, tmp_state):
        tmp_state.write_stage(StageName.SCRAPING, {"x": 1}, status=StageStatus.RUNNING)
        env = tmp_state.read_envelope(StageName.SCRAPING)
        assert env["status"] == StageStatus.RUNNING.value
        assert env["stage"] == StageName.SCRAPING.value

    def test_checkpoint_filename(self):
        assert StageName.CONFIG.filename == "stage1_config.json"
        assert StageName.SCRAPING.filename == "stage2_scraping.json"
        assert StageName.PLANNING.filename == "stage3_planning.json"
        assert StageName.EXPORT.filename == "stage4_export.json"

    def test_resolve_resume_from_aliases(self, tmp_state):
        assert tmp_state.resolve_resume_from("1") == StageName.CONFIG
        assert tmp_state.resolve_resume_from("scraping") == StageName.SCRAPING
        assert tmp_state.resolve_resume_from("plan") == StageName.PLANNING
        assert tmp_state.resolve_resume_from("export") == StageName.EXPORT

    def test_resolve_resume_from_invalid(self, tmp_state):
        with pytest.raises(ValueError, match="Unknown stage"):
            tmp_state.resolve_resume_from("unknown")

    def test_stages_to_run_full(self, tmp_state):
        stages = tmp_state.stages_to_run()
        assert stages == list(StageName)

    def test_stages_to_run_resume_skips_done(self, tmp_state):
        tmp_state.write_stage(StageName.CONFIG, {})
        tmp_state.mark_done(StageName.CONFIG)
        stages = tmp_state.stages_to_run(StageName.SCRAPING)
        assert StageName.CONFIG not in stages
        assert StageName.SCRAPING in stages

    def test_stages_to_run_blocks_if_prev_not_done(self, tmp_state):
        # CONFIG not done, cannot resume from SCRAPING
        with pytest.raises(ValueError, match="not done yet"):
            tmp_state.stages_to_run(StageName.SCRAPING)

    def test_summary(self, tmp_state):
        summary = tmp_state.summary()
        assert set(summary.keys()) == set(StageName)
        assert all(v == StageStatus.PENDING for v in summary.values())
