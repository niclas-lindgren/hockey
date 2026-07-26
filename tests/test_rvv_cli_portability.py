from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from tournament_scheduler.cli.args import build_parser
from tournament_scheduler.cli.reporting import _build_status_text
from tournament_scheduler.pipeline.state import PipelineState, StageName, StageStatus


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "rvv-miniputt"


def test_run_parser_accepts_portable_slash_command_flags() -> None:
    args = build_parser().parse_args(
        [
            "run",
            "--resume-from",
            "3",
            "--log-level",
            "verbose",
            "--force-refresh",
            "--work-dir",
            ".pipeline",
        ]
    )

    assert args.command == "run"
    assert args.resume_from == "3"
    assert args.log_level == "verbose"
    assert args.force_refresh is True


def test_run_parser_accepts_scrape_llm_flags() -> None:
    args = build_parser().parse_args(
        [
            "scrape-llm",
            "--club",
            "Holmen",
            "--work-dir",
            ".pipeline",
            "--export-dir",
            "export",
            "--endpoint",
            "http://localhost:1234",
            "--model",
            "qwen2.5-32b-instruct",
            "--max-iterations",
            "12",
            "--no-cache-results",
            "--debug-screenshots",
        ]
    )

    assert args.command == "scrape-llm"
    assert args.club == "Holmen"
    assert args.work_dir == ".pipeline"
    assert args.export_dir == "export"
    assert args.endpoint == "http://localhost:1234"
    assert args.model == "qwen2.5-32b-instruct"
    assert args.max_iterations == 12
    assert args.cache_results is False
    assert args.debug_screenshots is True


def test_repo_local_script_is_executable_and_shows_status() -> None:
    assert SCRIPT.exists()
    assert os.access(SCRIPT, os.X_OK)

    result = subprocess.run(
        [str(SCRIPT), "status"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Pipeline work-dir:" in result.stdout
    assert "Stage 1 (Config):" in result.stdout


def test_status_marks_downstream_stale_when_input_workbook_fingerprint_changes(tmp_path) -> None:
    input_file = tmp_path / "input.xlsx"
    input_file.write_bytes(b"old workbook bytes")
    old_sha = hashlib.sha256(b"old workbook bytes").hexdigest()
    work_dir = tmp_path / "pipeline"
    state = PipelineState(work_dir)
    state.write_stage(
        StageName.CONFIG,
        {
            "input_path": str(input_file),
            "input_fingerprint": {
                "algorithm": "sha256",
                "path": str(input_file),
                "sha256": old_sha,
            },
            "effective_config_fingerprint": {
                "algorithm": "sha256",
                "sha256": "old-effective",
            },
        },
        status=StageStatus.DONE,
    )
    state.write_stage(StageName.SCRAPING, {"sources": []}, status=StageStatus.DONE)
    state.write_stage(StageName.PLANNING, {"plan": {"tournaments": []}}, status=StageStatus.DONE)
    state.write_stage(StageName.EXPORT, {"output_files": {"excel": "plan.xlsx"}}, status=StageStatus.DONE)

    input_file.write_bytes(b"new workbook bytes")

    output = _build_status_text(work_dir)

    assert "Stage 2 (Scraping): failed" in output
    assert "stale from config" in output
    assert "Stage 4 (Export): failed" in output
    assert PipelineState(work_dir).is_stale(StageName.EXPORT)


def test_logs_list_subcommand_is_available_from_python_cli(tmp_path) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    run_id = "run-20260101_120000"
    (log_dir / f"{run_id}.jsonl").write_text(
        '{"type": "run_meta", "run_id": "run-20260101_120000", '
        '"exit_status": "success", "start_time": "2026-01-01T12:00:00", '
        '"end_time": "2026-01-01T12:01:00", "duration_ms": 60000}\n',
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable, "-m", "tournament_scheduler.cli.rvv_cli",
            "logs", "list", "--count", "1", "--work-dir", str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Pipeline kjøringshistorie" in result.stdout
    assert "run-" in result.stdout


def test_scrape_llm_cli_prints_browser_tool_guidance() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tournament_scheduler.cli.rvv_cli",
            "scrape-llm",
            "--club",
            "Holmen",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "browser-verktøy" in result.stdout
    assert "Playwright" in result.stdout
    assert "browser_worker" in result.stdout
    assert "/rvv-miniputt scrape-llm" in result.stdout
