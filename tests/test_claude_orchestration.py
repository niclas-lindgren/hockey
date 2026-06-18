"""
Integration tests for the stage-by-stage Claude Code orchestration flow.

Runs each pipeline stage module via subprocess (matching the python -m invocations
documented in .claude/commands/rvv-miniputt/run.md) and verifies the checkpoint
JSON written to .pipeline/ after each stage.

These tests use a temporary .pipeline/ directory and the real input.xlsx, but
pass --non-strict and --allow-missing-sources to stage 2 so no live calendar
scraping is required.

Tests are marked with pytest.mark.integration so they can be skipped in
environments where the full Python environment is not available.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
INPUT_XLSX = PROJECT_ROOT / "input.xlsx"


def _run_stage(
    module: str,
    work_dir: Path,
    extra_args: list[str] | None = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    """Invoke a pipeline stage module with python -m and return the result."""
    cmd = [
        sys.executable,
        "-m",
        module,
        "--work-dir",
        str(work_dir),
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=timeout)


def _load_checkpoint(work_dir: Path, filename: str) -> dict:
    path = work_dir / filename
    assert path.exists(), f"Checkpoint {filename} not found in {work_dir}"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data


# ---------------------------------------------------------------------------
# Skip if input.xlsx is missing (CI without fixture data)
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    not INPUT_XLSX.exists(),
    reason="input.xlsx not found — integration tests require a populated input workbook",
)


# ---------------------------------------------------------------------------
# Stage 1 — Config
# ---------------------------------------------------------------------------


class TestStage1Config:
    def test_stage1_writes_checkpoint(self, tmp_path: Path) -> None:
        result = _run_stage(
            "tournament_scheduler.pipeline.stage1_config",
            tmp_path,
            extra_args=["--input", str(INPUT_XLSX)],
        )
        assert result.returncode == 0, (
            f"Stage 1 exited with {result.returncode}.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        cp = _load_checkpoint(tmp_path, "stage1_config.json")
        assert cp.get("status") in ("done", "DONE"), f"Expected status=done, got: {cp.get('status')}"
        assert cp.get("stage") in ("config", "stage1_config"), f"Unexpected stage value: {cp.get('stage')}"
        assert "updated_at" in cp

    def test_stage1_checkpoint_has_expected_data_keys(self, tmp_path: Path) -> None:
        _run_stage(
            "tournament_scheduler.pipeline.stage1_config",
            tmp_path,
            extra_args=["--input", str(INPUT_XLSX)],
        )
        cp = _load_checkpoint(tmp_path, "stage1_config.json")
        data = cp.get("data") or {}
        assert "teams" in data, f"Expected 'teams' in stage1 data, got keys: {list(data.keys())}"
        assert isinstance(data["teams"], list), "'teams' should be a list"
        assert len(data["teams"]) > 0, "'teams' list should not be empty"

    def test_stage1_missing_input_exits_nonzero(self, tmp_path: Path) -> None:
        result = _run_stage(
            "tournament_scheduler.pipeline.stage1_config",
            tmp_path,
            extra_args=["--input", str(tmp_path / "nonexistent.xlsx")],
        )
        assert result.returncode != 0, "Expected non-zero exit for missing input file"


# ---------------------------------------------------------------------------
# Stage 2 — Scraping (no live network; uses --non-strict --allow-missing-sources)
# ---------------------------------------------------------------------------


class TestStage2Scraping:
    def _run_stage1(self, tmp_path: Path) -> None:
        result = _run_stage(
            "tournament_scheduler.pipeline.stage1_config",
            tmp_path,
            extra_args=["--input", str(INPUT_XLSX)],
        )
        assert result.returncode == 0, f"Stage 1 prerequisite failed.\nstderr: {result.stderr}"

    def test_stage2_writes_checkpoint_after_stage1(self, tmp_path: Path) -> None:
        self._run_stage1(tmp_path)
        result = _run_stage(
            "tournament_scheduler.pipeline.stage2_scraping",
            tmp_path,
            extra_args=["--non-strict", "--allow-missing-sources"],
        )
        assert result.returncode == 0, (
            f"Stage 2 exited with {result.returncode}.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        cp = _load_checkpoint(tmp_path, "stage2_scraping.json")
        assert cp.get("status") in ("done", "DONE"), f"Expected status=done, got: {cp.get('status')}"

    def test_stage2_checkpoint_has_expected_data_keys(self, tmp_path: Path) -> None:
        self._run_stage1(tmp_path)
        _run_stage(
            "tournament_scheduler.pipeline.stage2_scraping",
            tmp_path,
            extra_args=["--non-strict", "--allow-missing-sources"],
        )
        cp = _load_checkpoint(tmp_path, "stage2_scraping.json")
        data = cp.get("data") or {}
        assert "sources" in data, f"Expected 'sources' in stage2 data, got keys: {list(data.keys())}"
        assert isinstance(data["sources"], list), "'sources' should be a list"

    def test_stage2_reads_stage1_checkpoint(self, tmp_path: Path) -> None:
        """Stage 2 must be able to proceed using only the stage1 checkpoint on disk."""
        self._run_stage1(tmp_path)
        # Confirm stage1 checkpoint exists before stage2 runs
        assert (tmp_path / "stage1_config.json").exists(), "stage1_config.json missing before stage2"
        result = _run_stage(
            "tournament_scheduler.pipeline.stage2_scraping",
            tmp_path,
            extra_args=["--non-strict", "--allow-missing-sources"],
        )
        assert result.returncode == 0, f"Stage 2 failed to read stage1 checkpoint.\nstderr: {result.stderr}"


# ---------------------------------------------------------------------------
# Stage 3 — Planning
# ---------------------------------------------------------------------------


class TestStage3Planning:
    def _run_stages_1_and_2(self, tmp_path: Path) -> None:
        r1 = _run_stage(
            "tournament_scheduler.pipeline.stage1_config",
            tmp_path,
            extra_args=["--input", str(INPUT_XLSX)],
        )
        assert r1.returncode == 0, f"Stage 1 prerequisite failed.\nstderr: {r1.stderr}"
        r2 = _run_stage(
            "tournament_scheduler.pipeline.stage2_scraping",
            tmp_path,
            extra_args=["--non-strict", "--allow-missing-sources"],
        )
        assert r2.returncode == 0, f"Stage 2 prerequisite failed.\nstderr: {r2.stderr}"

    def test_stage3_writes_checkpoint(self, tmp_path: Path) -> None:
        self._run_stages_1_and_2(tmp_path)
        result = _run_stage("tournament_scheduler.pipeline.stage3_planning", tmp_path)
        assert result.returncode == 0, (
            f"Stage 3 exited with {result.returncode}.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        cp = _load_checkpoint(tmp_path, "stage3_planning.json")
        assert cp.get("status") in ("done", "DONE"), f"Expected status=done, got: {cp.get('status')}"

    def test_stage3_checkpoint_has_plan(self, tmp_path: Path) -> None:
        self._run_stages_1_and_2(tmp_path)
        _run_stage("tournament_scheduler.pipeline.stage3_planning", tmp_path)
        cp = _load_checkpoint(tmp_path, "stage3_planning.json")
        data = cp.get("data") or {}
        assert "plan" in data, f"Expected 'plan' in stage3 data, got keys: {list(data.keys())}"

    def test_stage3_reads_stage2_checkpoint(self, tmp_path: Path) -> None:
        """Stage 3 must pick up the stage2 checkpoint without re-running stage2."""
        self._run_stages_1_and_2(tmp_path)
        assert (tmp_path / "stage2_scraping.json").exists(), "stage2_scraping.json missing before stage3"
        result = _run_stage("tournament_scheduler.pipeline.stage3_planning", tmp_path)
        assert result.returncode == 0, f"Stage 3 failed to read stage2 checkpoint.\nstderr: {result.stderr}"


# ---------------------------------------------------------------------------
# Stage 4 — Export
# ---------------------------------------------------------------------------


class TestStage4Export:
    def _run_stages_1_through_3(self, tmp_path: Path) -> None:
        r1 = _run_stage(
            "tournament_scheduler.pipeline.stage1_config",
            tmp_path,
            extra_args=["--input", str(INPUT_XLSX)],
        )
        assert r1.returncode == 0, f"Stage 1 prerequisite failed.\nstderr: {r1.stderr}"
        r2 = _run_stage(
            "tournament_scheduler.pipeline.stage2_scraping",
            tmp_path,
            extra_args=["--non-strict", "--allow-missing-sources"],
        )
        assert r2.returncode == 0, f"Stage 2 prerequisite failed.\nstderr: {r2.stderr}"
        r3 = _run_stage("tournament_scheduler.pipeline.stage3_planning", tmp_path)
        assert r3.returncode == 0, f"Stage 3 prerequisite failed.\nstderr: {r3.stderr}"

    def test_stage4_writes_checkpoint(self, tmp_path: Path) -> None:
        self._run_stages_1_through_3(tmp_path)
        export_dir = tmp_path / "export"
        result = _run_stage(
            "tournament_scheduler.pipeline.stage4_export",
            tmp_path,
            extra_args=["--export-dir", str(export_dir), "--no-timestamped-export"],
        )
        assert result.returncode == 0, (
            f"Stage 4 exited with {result.returncode}.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        cp = _load_checkpoint(tmp_path, "stage4_export.json")
        assert cp.get("status") in ("done", "DONE"), f"Expected status=done, got: {cp.get('status')}"

    def test_stage4_reads_stage3_checkpoint(self, tmp_path: Path) -> None:
        """Stage 4 must pick up the stage3 checkpoint without re-running planning."""
        self._run_stages_1_through_3(tmp_path)
        assert (tmp_path / "stage3_planning.json").exists(), "stage3_planning.json missing before stage4"
        export_dir = tmp_path / "export"
        result = _run_stage(
            "tournament_scheduler.pipeline.stage4_export",
            tmp_path,
            extra_args=["--export-dir", str(export_dir), "--no-timestamped-export"],
        )
        assert result.returncode == 0, f"Stage 4 failed to read stage3 checkpoint.\nstderr: {result.stderr}"


# ---------------------------------------------------------------------------
# Checkpoint printer
# ---------------------------------------------------------------------------


class TestCheckpointPrinter:
    def test_checkpoint_printer_stage1(self, tmp_path: Path) -> None:
        _run_stage(
            "tournament_scheduler.pipeline.stage1_config",
            tmp_path,
            extra_args=["--input", str(INPUT_XLSX)],
        )
        result = subprocess.run(
            [sys.executable, "-m", "tournament_scheduler.cli.checkpoint_printer", "stage1", "--work-dir", str(tmp_path)],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, f"checkpoint_printer exited non-zero.\nstderr: {result.stderr}"
        assert "Stage 1" in result.stdout
        assert "status" in result.stdout.lower()

    def test_checkpoint_printer_unknown_stage_exits_nonzero(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "tournament_scheduler.cli.checkpoint_printer", "badstage", "--work-dir", str(tmp_path)],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode != 0, "Expected non-zero exit for unknown stage"

    def test_checkpoint_printer_missing_checkpoint_exits_nonzero(self, tmp_path: Path) -> None:
        # No stages run, so no checkpoint files exist
        result = subprocess.run(
            [sys.executable, "-m", "tournament_scheduler.cli.checkpoint_printer", "stage1", "--work-dir", str(tmp_path)],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode != 0, "Expected non-zero exit for missing checkpoint"
