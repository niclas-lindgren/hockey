from __future__ import annotations

import json
from pathlib import Path

from tournament_scheduler.cli import reporting
from tournament_scheduler.pipeline.run_log_paths import resolve_active_run_log_dir
from tournament_scheduler.pipeline.state import PipelineState, StageName, StageStatus


def _write_run_log(path: Path, *, run_id: str, status: str) -> None:
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "run_meta",
                        "run_id": run_id,
                        "start_time": "2026-07-27T22:30:00+00:00",
                        "end_time": "2026-07-27T22:31:00+00:00",
                        "duration_ms": 60000,
                        "exit_status": status,
                    },
                    ensure_ascii=False,
                )
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_resolve_active_run_log_dir_prefers_stage4_export_output_files(tmp_path: Path) -> None:
    work_dir = tmp_path / ".pipeline"
    state = PipelineState(work_dir)

    export_dir = tmp_path / "export" / "2026-07-27T2230"
    export_dir.mkdir(parents=True)
    state.write_stage(
        StageName.EXPORT,
        {"output_files": {"excel": str(export_dir / "season_plan.xlsx")}},
        status=StageStatus.DONE,
    )

    legacy_log_dir = work_dir / "logs"
    legacy_log_dir.mkdir(parents=True)
    (legacy_log_dir / "run-legacy.jsonl").write_text("legacy\n", encoding="utf-8")

    assert resolve_active_run_log_dir(state) == export_dir


def test_logs_reporting_prefers_export_tree_over_legacy_workspace_logs(tmp_path: Path) -> None:
    work_dir = tmp_path / ".pipeline"
    state = PipelineState(work_dir)

    export_dir = tmp_path / "export" / "2026-07-27T2230"
    export_dir.mkdir(parents=True)
    state.write_stage(
        StageName.EXPORT,
        {"output_files": {"excel": str(export_dir / "season_plan.xlsx")}},
        status=StageStatus.DONE,
    )

    export_log = export_dir / "run-shared.jsonl"
    _write_run_log(export_log, run_id="run-shared", status="success")

    legacy_log_dir = work_dir / "logs"
    legacy_log_dir.mkdir(parents=True)
    legacy_log = legacy_log_dir / "run-shared.jsonl"
    _write_run_log(legacy_log, run_id="run-shared", status="failure")

    list_text = reporting._build_logs_list_text(work_dir, 10)
    show_text = reporting._build_logs_show_text(work_dir, "run-shared")
    stats_text = reporting._build_logs_stats_text(work_dir)

    assert str(export_dir) in list_text
    assert "failure" not in list_text
    assert "Status:      success" in show_text
    assert "failure" not in show_text
    assert "Totalt antall kjøringer: 1" in stats_text
    assert "Feil:                    0" in stats_text
