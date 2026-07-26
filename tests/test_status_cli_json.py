"""Unit tests for ``rvv-miniputt status --json``."""
from __future__ import annotations

import argparse
import json

from tournament_scheduler.cli.reporting import _cmd_status
from tournament_scheduler.pipeline.capability_result import CapabilityResult
from tournament_scheduler.pipeline.run_manifest import RunManifest


def _status_args(work_dir: str, *, as_json: bool) -> argparse.Namespace:
    return argparse.Namespace(work_dir=work_dir, json=as_json)


def test_status_json_prints_run_manifest(tmp_path, capsys):
    work_dir = tmp_path / "pipeline"
    manifest = RunManifest(work_dir)
    manifest.start_run("Produce the best trustworthy season plan")
    manifest.record_capability(CapabilityResult.ok("4 sources configured", capability="config"))
    manifest.finalize("ok")

    rc = _cmd_status(_status_args(str(work_dir), as_json=True))
    assert rc == 0

    printed = json.loads(capsys.readouterr().out)
    assert printed["objective"] == "Produce the best trustworthy season plan"
    assert printed["final_outcome"] == "ok"
    assert printed["capabilities"][0]["capability"] == "config"


def test_status_json_without_manifest_falls_back_to_synthesized_view(tmp_path, capsys):
    work_dir = tmp_path / "pipeline"
    work_dir.mkdir()

    rc = _cmd_status(_status_args(str(work_dir), as_json=True))
    assert rc == 0

    printed = json.loads(capsys.readouterr().out)
    assert printed["synthesized_from_legacy_checkpoints"] is True


def test_status_without_json_flag_prints_human_readable_text(tmp_path, capsys):
    work_dir = tmp_path / "pipeline"
    rc = _cmd_status(_status_args(str(work_dir), as_json=False))
    assert rc == 0
    out = capsys.readouterr().out
    assert "Pipeline work-dir" in out
