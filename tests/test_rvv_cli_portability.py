from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from tournament_scheduler.cli.args import build_parser


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


def test_logs_list_subcommand_is_available_from_python_cli() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tournament_scheduler.cli.rvv_cli", "logs", "list", "--count", "1"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Pipeline kjøringshistorie" in result.stdout
    assert "run-" in result.stdout
