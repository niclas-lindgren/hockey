"""Tests for the goal-oriented AI operator entry point (``rvv-miniputt operator run``)."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tournament_scheduler.cli.args import build_parser
from tournament_scheduler.cli.pipeline_orchestrator import (
    _DEFAULT_OPERATOR_OBJECTIVE,
    _cmd_operator_run,
    _resolve_operator_resume_stage,
)
from tournament_scheduler.cli.rvv_cli import _cmd_operator
from tournament_scheduler.pipeline.run_manifest import RunManifest
from tournament_scheduler.pipeline.state import PipelineState, StageName, StageStatus


# ---------------------------------------------------------------------------
# _resolve_operator_resume_stage
# ---------------------------------------------------------------------------


def test_resolve_resume_stage_all_pending_returns_1(tmp_path):
    state = PipelineState(tmp_path)
    assert _resolve_operator_resume_stage(state) == 1


def test_resolve_resume_stage_partial_progress_returns_earliest_pending(tmp_path):
    state = PipelineState(tmp_path)
    state.write_stage(StageName.CONFIG, {"sources": []}, status=StageStatus.DONE)
    assert _resolve_operator_resume_stage(state) == 2


def test_resolve_resume_stage_stale_stage_is_treated_as_pending(tmp_path):
    state = PipelineState(tmp_path)
    state.write_stage(StageName.CONFIG, {"a": 1}, status=StageStatus.DONE)
    state.write_stage(StageName.SCRAPING, {"sources": []}, status=StageStatus.DONE)
    state.write_stage(StageName.PLANNING, {"plan": {}}, status=StageStatus.DONE)
    state.write_stage(StageName.EXPORT, {"output_files": {}}, status=StageStatus.DONE)
    # Rewriting CONFIG as done invalidates (stales) everything downstream.
    state.write_stage(StageName.CONFIG, {"a": 2}, status=StageStatus.DONE)
    assert _resolve_operator_resume_stage(state) == 2


def test_resolve_resume_stage_all_done_returns_none(tmp_path):
    state = PipelineState(tmp_path)
    for stage in (StageName.CONFIG, StageName.SCRAPING, StageName.PLANNING, StageName.EXPORT):
        state.write_stage(stage, {"x": 1}, status=StageStatus.DONE)
    assert _resolve_operator_resume_stage(state) is None


# ---------------------------------------------------------------------------
# _cmd_operator_run
# ---------------------------------------------------------------------------


def _operator_args(tmp_path: Path, **overrides) -> argparse.Namespace:
    defaults = dict(
        work_dir=str(tmp_path),
        input="input.xlsx",
        export_dir="export",
        objective=None,
        resume_from=None,
        force=False,
        log_level="info",
        force_refresh=False,
        non_strict=False,
        allow_missing_sources=False,
        timestamped_export=True,
        iterations=1,
        mid_planning_critic_iterations=0,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_nothing_pending_skips_the_pipeline_entirely(tmp_path):
    state = PipelineState(tmp_path)
    for stage in (StageName.CONFIG, StageName.SCRAPING, StageName.PLANNING, StageName.EXPORT):
        state.write_stage(stage, {"x": 1}, status=StageStatus.DONE)

    args = _operator_args(tmp_path)
    with patch("tournament_scheduler.cli.pipeline_orchestrator._cmd_run") as mock_run:
        rc = _cmd_operator_run(args)

    mock_run.assert_not_called()
    assert rc == 0


def test_empty_workspace_auto_resumes_from_stage_1(tmp_path):
    args = _operator_args(tmp_path)
    with patch("tournament_scheduler.cli.pipeline_orchestrator._cmd_run", return_value=0) as mock_run:
        rc = _cmd_operator_run(args)

    mock_run.assert_called_once()
    called_args = mock_run.call_args[0][0]
    assert called_args.resume_from == "1"
    assert called_args.objective == _DEFAULT_OPERATOR_OBJECTIVE
    assert rc == 0


def test_partial_progress_auto_resumes_from_earliest_pending_stage(tmp_path):
    state = PipelineState(tmp_path)
    state.write_stage(StageName.CONFIG, {"a": 1}, status=StageStatus.DONE)
    state.write_stage(StageName.SCRAPING, {"sources": []}, status=StageStatus.DONE)

    args = _operator_args(tmp_path)
    with patch("tournament_scheduler.cli.pipeline_orchestrator._cmd_run", return_value=0) as mock_run:
        _cmd_operator_run(args)

    called_args = mock_run.call_args[0][0]
    assert called_args.resume_from == "3"


def test_explicit_resume_from_overrides_auto_detection(tmp_path):
    args = _operator_args(tmp_path, resume_from="4")
    with patch("tournament_scheduler.cli.pipeline_orchestrator._cmd_run", return_value=0) as mock_run:
        _cmd_operator_run(args)

    called_args = mock_run.call_args[0][0]
    assert called_args.resume_from == "4"


def test_force_flag_reruns_from_stage_1_even_when_all_done(tmp_path):
    state = PipelineState(tmp_path)
    for stage in (StageName.CONFIG, StageName.SCRAPING, StageName.PLANNING, StageName.EXPORT):
        state.write_stage(stage, {"x": 1}, status=StageStatus.DONE)

    args = _operator_args(tmp_path, force=True)
    with patch("tournament_scheduler.cli.pipeline_orchestrator._cmd_run", return_value=0) as mock_run:
        rc = _cmd_operator_run(args)

    mock_run.assert_called_once()
    called_args = mock_run.call_args[0][0]
    assert called_args.resume_from == "1"
    assert rc == 0


def test_custom_objective_is_passed_through(tmp_path):
    args = _operator_args(tmp_path, objective="Fill in the gap for U12")
    with patch("tournament_scheduler.cli.pipeline_orchestrator._cmd_run", return_value=0) as mock_run:
        _cmd_operator_run(args)

    called_args = mock_run.call_args[0][0]
    assert called_args.objective == "Fill in the gap for U12"


def test_propagates_cmd_run_exit_code(tmp_path):
    args = _operator_args(tmp_path)
    with patch("tournament_scheduler.cli.pipeline_orchestrator._cmd_run", return_value=1):
        rc = _cmd_operator_run(args)
    assert rc == 1


def test_prints_final_summary_from_run_manifest(tmp_path, capsys):
    from tournament_scheduler.pipeline.capability_result import CapabilityResult

    manifest = RunManifest(tmp_path)
    manifest.start_run("Produce the best trustworthy season plan")
    manifest.record_capability(CapabilityResult.ok("done", capability="config"))
    manifest.finalize("ok")

    args = _operator_args(tmp_path)
    with patch("tournament_scheduler.cli.pipeline_orchestrator._cmd_run", return_value=0):
        _cmd_operator_run(args)

    out = capsys.readouterr().out
    assert "Operator-sammendrag" in out
    assert "OK" in out
    assert "config" in out


# ---------------------------------------------------------------------------
# CLI argument parsing and dispatch
# ---------------------------------------------------------------------------


def test_parser_accepts_operator_run_with_objective():
    args = build_parser().parse_args(
        ["operator", "run", "--objective", "Custom goal", "--work-dir", ".pipeline"]
    )
    assert args.command == "operator"
    assert args.operator_command == "run"
    assert args.objective == "Custom goal"
    assert args.resume_from is None
    assert args.force is False


def test_parser_defaults_objective_to_none():
    args = build_parser().parse_args(["operator", "run"])
    assert args.objective is None


def test_cmd_operator_dispatches_to_run():
    args = argparse.Namespace(operator_command="run")
    with patch("tournament_scheduler.cli.rvv_cli._cmd_operator_run", return_value=0) as mock_run:
        rc = _cmd_operator(args)
    mock_run.assert_called_once_with(args)
    assert rc == 0


def test_cmd_operator_without_subcommand_prints_usage():
    args = argparse.Namespace(operator_command=None)
    rc = _cmd_operator(args)
    assert rc == 1


# ---------------------------------------------------------------------------
# End-to-end: real _cmd_run (not mocked), all stage functions stubbed
# ---------------------------------------------------------------------------

_MINIMAL_CFG = {
    "sources": [],
    "start_date": "2026-01-01",
    "end_date": "2026-12-31",
    "age_groups": [],
    "clubs": [],
}
_MINIMAL_SCRAPING = {"sources": [], "blocked": [], "llm_fallback": []}
_MINIMAL_PLAN = {"plan": {"tournaments": []}, "warnings": []}
_MINIMAL_EXPORT = {"output_files": {}}


def test_end_to_end_writes_run_manifest_with_objective_and_capabilities(tmp_path):
    args = _operator_args(tmp_path, objective="Fyll sesongen for U10")

    with patch("tournament_scheduler.pipeline.stage1_config.run", return_value=None), \
         patch("tournament_scheduler.pipeline.stage1_config.load_effective_config", return_value=_MINIMAL_CFG), \
         patch("tournament_scheduler.pipeline.stage2_scraping.run", return_value=_MINIMAL_SCRAPING), \
         patch("tournament_scheduler.pipeline.stage3_planning.run", return_value=_MINIMAL_PLAN), \
         patch("tournament_scheduler.pipeline.stage4_export.run", return_value=_MINIMAL_EXPORT), \
         patch("tournament_scheduler.pipeline.calendar_viewer.generate_html", return_value="export/calendars.html"):
        rc = _cmd_operator_run(args)

    assert rc == 0
    manifest = RunManifest(tmp_path).read()
    assert manifest["objective"] == "Fyll sesongen for U10"
    assert manifest["final_outcome"] == "ok"
    capability_names = [c["capability"] for c in manifest["capabilities"]]
    assert capability_names == ["config", "scraping", "planning", "export"]


def test_second_invocation_with_nothing_pending_does_not_rerun_stages(tmp_path):
    # Simulates the workspace state a *real* completed run would leave behind
    # (mocking stage1_config.run() etc. in the first test above bypasses their
    # own checkpoint-writing side effects, so it can't exercise this path).
    state = PipelineState(tmp_path)
    for stage in (StageName.CONFIG, StageName.SCRAPING, StageName.PLANNING, StageName.EXPORT):
        state.write_stage(stage, {"x": 1}, status=StageStatus.DONE)

    args = _operator_args(tmp_path)
    with patch("tournament_scheduler.pipeline.stage2_scraping.run") as stage2:
        rc = _cmd_operator_run(args)

    assert rc == 0
    stage2.assert_not_called()


# ---------------------------------------------------------------------------
# Recovery-loop wiring (issue #11): _cmd_operator_run must run the
# observe-decide-act loop before deciding where to resume from, and force a
# Stage 2 rerun when the loop actually repaired something, even if
# auto-detection would otherwise have seen "all done" or a later stage.
# ---------------------------------------------------------------------------


def test_recovery_loop_invoked_with_work_dir_before_run(tmp_path):
    args = _operator_args(tmp_path)
    with patch(
        "tournament_scheduler.cli.pipeline_orchestrator._run_recovery_loop", return_value=None
    ) as mock_recovery, patch(
        "tournament_scheduler.cli.pipeline_orchestrator._cmd_run", return_value=0
    ):
        _cmd_operator_run(args)

    mock_recovery.assert_called_once_with(str(tmp_path))


def test_recovery_loop_action_taken_forces_resume_to_stage_2_when_otherwise_all_done(tmp_path):
    state = PipelineState(tmp_path)
    for stage in (StageName.CONFIG, StageName.SCRAPING, StageName.PLANNING, StageName.EXPORT):
        state.write_stage(stage, {"x": 1}, status=StageStatus.DONE)

    args = _operator_args(tmp_path)
    recovery_summary = {
        "actions_taken": 1,
        "sources_resolved": ["Jar"],
        "sources_escalated": [],
        "stopped_reason": "completed",
    }
    with patch(
        "tournament_scheduler.cli.pipeline_orchestrator._run_recovery_loop",
        return_value=recovery_summary,
    ), patch("tournament_scheduler.cli.pipeline_orchestrator._cmd_run", return_value=0) as mock_run:
        rc = _cmd_operator_run(args)

    mock_run.assert_called_once()
    called_args = mock_run.call_args[0][0]
    assert called_args.resume_from == "2"
    assert rc == 0


def test_recovery_loop_action_taken_does_not_move_resume_later_than_earliest_pending(tmp_path):
    # Nothing at all has run yet, so auto-detection already wants stage 1 —
    # a recovered source must not push the resume point *later* to stage 2.
    args = _operator_args(tmp_path)
    recovery_summary = {
        "actions_taken": 1,
        "sources_resolved": [],
        "sources_escalated": [],
        "stopped_reason": "completed",
    }
    with patch(
        "tournament_scheduler.cli.pipeline_orchestrator._run_recovery_loop",
        return_value=recovery_summary,
    ), patch("tournament_scheduler.cli.pipeline_orchestrator._cmd_run", return_value=0) as mock_run:
        _cmd_operator_run(args)

    called_args = mock_run.call_args[0][0]
    assert called_args.resume_from == "1"


def test_recovery_loop_no_actions_taken_does_not_force_a_rerun(tmp_path):
    state = PipelineState(tmp_path)
    for stage in (StageName.CONFIG, StageName.SCRAPING, StageName.PLANNING, StageName.EXPORT):
        state.write_stage(stage, {"x": 1}, status=StageStatus.DONE)

    args = _operator_args(tmp_path)
    recovery_summary = {
        "actions_taken": 0,
        "sources_resolved": [],
        "sources_escalated": [],
        "stopped_reason": "completed",
    }
    with patch(
        "tournament_scheduler.cli.pipeline_orchestrator._run_recovery_loop",
        return_value=recovery_summary,
    ), patch("tournament_scheduler.cli.pipeline_orchestrator._cmd_run") as mock_run:
        rc = _cmd_operator_run(args)

    mock_run.assert_not_called()
    assert rc == 0


def test_recovery_loop_explicit_resume_from_wins_over_recovered_actions(tmp_path):
    args = _operator_args(tmp_path, resume_from="4")
    recovery_summary = {
        "actions_taken": 1,
        "sources_resolved": ["Jar"],
        "sources_escalated": [],
        "stopped_reason": "completed",
    }
    with patch(
        "tournament_scheduler.cli.pipeline_orchestrator._run_recovery_loop",
        return_value=recovery_summary,
    ), patch("tournament_scheduler.cli.pipeline_orchestrator._cmd_run", return_value=0) as mock_run:
        _cmd_operator_run(args)

    called_args = mock_run.call_args[0][0]
    assert called_args.resume_from == "4"


def test_recovery_loop_exception_degrades_to_normal_run_instead_of_crashing(tmp_path):
    # _run_recovery_loop itself must never propagate — a broken recovery
    # attempt should leave the human with the same blocked sources they
    # would have had anyway, not a crashed `operator run`.
    args = _operator_args(tmp_path)
    with patch(
        "tournament_scheduler.pipeline.operator_loop.run_source_recovery_loop",
        side_effect=RuntimeError("boom"),
    ), patch("tournament_scheduler.cli.pipeline_orchestrator._cmd_run", return_value=0) as mock_run:
        rc = _cmd_operator_run(args)

    mock_run.assert_called_once()
    assert rc == 0
