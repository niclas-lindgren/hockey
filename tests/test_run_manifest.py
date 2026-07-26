"""Tests for tournament_scheduler.pipeline.run_manifest (RunManifest)."""

import json

import pytest

from tournament_scheduler.pipeline.capability_result import CapabilityResult
from tournament_scheduler.pipeline.run_manifest import (
    RUN_MANIFEST_SCHEMA_VERSION,
    RunManifest,
)
from tournament_scheduler.pipeline.state import PipelineState, StageName, StageStatus


@pytest.fixture()
def manifest(tmp_path):
    return RunManifest(tmp_path / "pipeline")


class TestRunManifestLifecycle:
    def test_creates_work_dir(self, tmp_path):
        work_dir = tmp_path / "newdir"
        assert not work_dir.exists()
        RunManifest(work_dir)
        assert work_dir.exists()

    def test_start_run_writes_expected_shape(self, manifest):
        data = manifest.start_run("Produce the best season plan")
        assert data["schema_version"] == RUN_MANIFEST_SCHEMA_VERSION
        assert data["objective"] == "Produce the best season plan"
        assert data["final_outcome"] == "in_progress"
        assert data["current_capability"] is None
        assert data["capabilities"] == []
        assert data["run_id"]
        assert data["started_at"] == data["updated_at"]
        assert manifest.exists()

    def test_start_run_generates_unique_run_ids(self, manifest):
        first = manifest.start_run("objective A")
        second = manifest.start_run("objective B")
        assert first["run_id"] != second["run_id"]

    def test_records_input_fingerprint(self, manifest):
        data = manifest.start_run("objective", input_fingerprint={"path": "input.xlsx", "sha256": "abc123"})
        assert data["input_fingerprint"] == {"path": "input.xlsx", "sha256": "abc123"}

    def test_set_current_capability(self, manifest):
        manifest.start_run("objective")
        manifest.set_current_capability("scraping")
        assert manifest.read()["current_capability"] == "scraping"


class TestRunManifestCapabilityOutcomes:
    @pytest.mark.parametrize("status", ["ok", "warning", "blocked", "failed"])
    def test_record_capability_for_each_status(self, manifest, status):
        manifest.start_run("objective")
        result = CapabilityResult(status=status, summary=f"stage returned {status}", capability="scraping")
        entry = manifest.record_capability(result)

        assert entry["status"] == status
        assert entry["recorded_at"]

        data = manifest.read()
        assert len(data["capabilities"]) == 1
        assert data["capabilities"][0]["status"] == status
        assert data["current_capability"] == "scraping"

    def test_record_capability_appends_history(self, manifest):
        manifest.start_run("objective")
        manifest.record_capability(CapabilityResult.ok("config ready", capability="config"))
        manifest.record_capability(CapabilityResult.warning("1 source blocked", capability="scraping"))
        data = manifest.read()
        assert [c["capability"] for c in data["capabilities"]] == ["config", "scraping"]

    @pytest.mark.parametrize("outcome", ["ok", "warning", "blocked", "failed"])
    def test_finalize_sets_terminal_outcome(self, manifest, outcome):
        manifest.start_run("objective")
        manifest.finalize(outcome)
        data = manifest.read()
        assert data["final_outcome"] == outcome
        assert data["ended_at"] is not None

    def test_finalize_rejects_in_progress(self, manifest):
        manifest.start_run("objective")
        with pytest.raises(ValueError):
            manifest.finalize("in_progress")

    def test_finalize_rejects_unknown_outcome(self, manifest):
        manifest.start_run("objective")
        with pytest.raises(ValueError):
            manifest.finalize("not-a-real-outcome")


class TestRunManifestJsonOnDisk:
    def test_manifest_file_is_valid_json(self, manifest):
        manifest.start_run("objective")
        manifest.record_capability(CapabilityResult.ok("done", capability="config"))
        raw = json.loads(manifest.path.read_text(encoding="utf-8"))
        assert raw["objective"] == "objective"


class TestRunManifestBackwardCompatibility:
    def test_read_with_no_manifest_synthesizes_from_legacy_checkpoints(self, tmp_path):
        work_dir = tmp_path / "pipeline"
        state = PipelineState(work_dir)
        state.write_stage(StageName.CONFIG, {"teams": ["A", "B"]}, status=StageStatus.DONE)
        state.write_stage(StageName.SCRAPING, {"sources": []}, status=StageStatus.DONE)

        manifest = RunManifest(work_dir)
        assert not manifest.exists()
        data = manifest.read()

        assert data["schema_version"] == RUN_MANIFEST_SCHEMA_VERSION
        assert data["synthesized_from_legacy_checkpoints"] is True
        assert data["run_id"] == "legacy"
        assert [c["capability"] for c in data["capabilities"]] == ["config", "scraping"]
        assert all(c["status"] == "ok" for c in data["capabilities"])
        assert data["current_capability"] == "scraping"

    def test_synthesized_manifest_reflects_failed_stage(self, tmp_path):
        work_dir = tmp_path / "pipeline"
        state = PipelineState(work_dir)
        state.write_stage(StageName.CONFIG, {"teams": ["A"]}, status=StageStatus.DONE)
        state.write_stage(StageName.SCRAPING, {"sources": []}, status=StageStatus.FAILED)
        state.mark_failed(StageName.SCRAPING, error="network error")

        data = RunManifest(work_dir).read()
        capability_by_name = {c["capability"]: c for c in data["capabilities"]}
        assert capability_by_name["scraping"]["status"] == "failed"
        assert data["final_outcome"] == "failed"

    def test_read_with_no_checkpoints_at_all(self, tmp_path):
        data = RunManifest(tmp_path / "pipeline").read()
        assert data["capabilities"] == []
        assert data["final_outcome"] == "in_progress"

    def test_read_with_corrupt_manifest_file_falls_back(self, tmp_path):
        work_dir = tmp_path / "pipeline"
        manifest = RunManifest(work_dir)
        manifest.path.write_text("not valid json{{{", encoding="utf-8")
        data = manifest.read()
        assert data["synthesized_from_legacy_checkpoints"] is True
