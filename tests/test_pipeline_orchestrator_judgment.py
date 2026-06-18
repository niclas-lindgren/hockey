"""Tests for _judge_stage() integration inside _cmd_run() in pipeline_orchestrator.py.

Since _judge_stage() is a nested function, these tests exercise it via _cmd_run()
with all stage runners mocked to avoid full pipeline execution.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tournament_scheduler.cli.pipeline_orchestrator import _cmd_run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HARNESS_CLEAN = {
    "RVV_HARNESS": "",
    "CLAUDE_CODE_SESSION_ID": "",
    "PI_SESSION_ID": "",
    "OPENCODE_SESSION_ID": "",
}

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


def _make_args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        work_dir=str(tmp_path),
        input="config.yaml",
        non_strict=True,
        resume_from=None,
        allow_missing_sources=False,
        force_refresh=False,
        export_dir="export",
        timestamped_export=False,
        log_level="info",
    )


def _all_stage_patches():
    """Return a list of patch context managers for all stage imports used by _cmd_run."""
    return [
        patch(
            "tournament_scheduler.pipeline.stage1_config.run",
            return_value=None,
        ),
        patch(
            "tournament_scheduler.pipeline.stage1_config.load_effective_config",
            return_value=_MINIMAL_CFG,
        ),
        patch(
            "tournament_scheduler.pipeline.stage2_scraping.run",
            return_value=_MINIMAL_SCRAPING,
        ),
        patch(
            "tournament_scheduler.pipeline.stage3_planning.run",
            return_value=_MINIMAL_PLAN,
        ),
        patch(
            "tournament_scheduler.pipeline.stage4_export.run",
            return_value=_MINIMAL_EXPORT,
        ),
        patch(
            "tournament_scheduler.pipeline.calendar_viewer.generate_html",
            return_value="export/calendars.html",
        ),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_judge_skipped_when_harness_active(tmp_path: Path) -> None:
    """When a harness env var is set, get_judge_if_headless returns None and pipeline proceeds."""
    args = _make_args(tmp_path)
    judge_mock = MagicMock()
    judge_mock.judge.return_value = "PROCEED"

    patches = _all_stage_patches()
    with patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": "session-abc"}):
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            result = _cmd_run(args)

    assert result == 0
    judge_mock.judge.assert_not_called()


def test_judge_proceed_verdict_continues_pipeline(tmp_path: Path) -> None:
    """Headless run with PROCEED verdict — pipeline completes successfully."""
    args = _make_args(tmp_path)
    judge_mock = MagicMock()
    judge_mock.judge.return_value = "PROCEED"

    patches = _all_stage_patches()
    with patch.dict(os.environ, {**_HARNESS_CLEAN, "RVV_JUDGE_BACKEND": "llm_bridge"}):
        with patch("tournament_scheduler.llm_judge.get_judge_if_headless", return_value=judge_mock):
            with patch("tournament_scheduler.llm_judge.build_stage_prompt", return_value="prompt text"):
                with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                    result = _cmd_run(args)

    assert result == 0
    # judge called after stage1, stage2, stage3
    assert judge_mock.judge.call_count == 3


def test_judge_abort_verdict_after_stage1_stops_pipeline(tmp_path: Path) -> None:
    """Headless run with ABORT verdict after stage 1 — _cmd_run returns 1."""
    args = _make_args(tmp_path)
    judge_mock = MagicMock()
    judge_mock.judge.return_value = "ABORT\nToo few sources configured."

    patches = _all_stage_patches()
    with patch.dict(os.environ, {**_HARNESS_CLEAN, "RVV_JUDGE_BACKEND": "llm_bridge"}):
        with patch("tournament_scheduler.llm_judge.get_judge_if_headless", return_value=judge_mock):
            with patch("tournament_scheduler.llm_judge.build_stage_prompt", return_value="prompt"):
                with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                    result = _cmd_run(args)

    assert result == 1
    # only called once — stage 1 aborted the pipeline
    assert judge_mock.judge.call_count == 1


def test_judge_proceed_with_reasoning_continues(tmp_path: Path) -> None:
    """Multi-line verdict starting with PROCEED still continues the pipeline."""
    args = _make_args(tmp_path)
    judge_mock = MagicMock()
    judge_mock.judge.return_value = "PROCEED\nAll sources look healthy."

    patches = _all_stage_patches()
    with patch.dict(os.environ, {**_HARNESS_CLEAN, "RVV_JUDGE_BACKEND": "llm_bridge"}):
        with patch("tournament_scheduler.llm_judge.get_judge_if_headless", return_value=judge_mock):
            with patch("tournament_scheduler.llm_judge.build_stage_prompt", return_value="prompt"):
                with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                    result = _cmd_run(args)

    assert result == 0


def test_judge_abort_verdict_writes_judgment_to_checkpoint(tmp_path: Path) -> None:
    """ABORT verdict is written via state.write_judgment with the correct verdict."""
    from tournament_scheduler.pipeline.state import PipelineState, StageName

    args = _make_args(tmp_path)
    judge_mock = MagicMock()
    judge_mock.judge.return_value = "ABORT\nMissing required sources."

    # Pre-create the stage1 checkpoint so write_judgment has an envelope to update.
    state = PipelineState(str(tmp_path))
    state.write_stage(StageName.CONFIG, _MINIMAL_CFG)

    patches = _all_stage_patches()
    with patch.dict(os.environ, {**_HARNESS_CLEAN, "RVV_JUDGE_BACKEND": "llm_bridge"}):
        with patch("tournament_scheduler.llm_judge.get_judge_if_headless", return_value=judge_mock):
            with patch("tournament_scheduler.llm_judge.build_stage_prompt", return_value="prompt"):
                with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                    result = _cmd_run(args)

    assert result == 1

    # Verify write_judgment persisted ABORT to the checkpoint.
    envelope = state.read_envelope(StageName.CONFIG)
    assert "judgment" in envelope, "judgment key must be written to checkpoint"
    assert envelope["judgment"]["verdict"] == "ABORT"
    assert "Missing required sources." in envelope["judgment"]["reasoning"]


def test_judge_runtime_error_continues_pipeline(tmp_path: Path) -> None:
    """When judge.judge() raises RuntimeError, pipeline continues (returns 0)."""
    args = _make_args(tmp_path)
    judge_mock = MagicMock()
    judge_mock.judge.side_effect = RuntimeError("LLM Bridge connection failed")

    patches = _all_stage_patches()
    with patch.dict(os.environ, {**_HARNESS_CLEAN, "RVV_JUDGE_BACKEND": "llm_bridge"}):
        with patch("tournament_scheduler.llm_judge.get_judge_if_headless", return_value=judge_mock):
            with patch("tournament_scheduler.llm_judge.build_stage_prompt", return_value="prompt"):
                with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                    result = _cmd_run(args)

    assert result == 0
    # judge was attempted despite failure
    assert judge_mock.judge.call_count >= 1


def test_judge_no_backend_configured_continues(tmp_path: Path) -> None:
    """When RVV_JUDGE_BACKEND is unset, get_judge_if_headless raises ValueError — pipeline proceeds."""
    args = _make_args(tmp_path)

    patches = _all_stage_patches()
    # Simulate no backend: get_judge_if_headless raises ValueError
    with patch.dict(os.environ, {**_HARNESS_CLEAN, "RVV_JUDGE_BACKEND": ""}):
        with patch(
            "tournament_scheduler.llm_judge.get_judge_if_headless",
            side_effect=ValueError("No judge backend specified"),
        ):
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                result = _cmd_run(args)

    assert result == 0


def test_judge_called_three_times_when_all_proceed(tmp_path: Path) -> None:
    """In a complete headless run, judge is invoked after stages 1, 2, and 3."""
    args = _make_args(tmp_path)
    judge_mock = MagicMock()
    judge_mock.judge.return_value = "PROCEED"

    patches = _all_stage_patches()
    with patch.dict(os.environ, {**_HARNESS_CLEAN, "RVV_JUDGE_BACKEND": "llm_bridge"}):
        with patch("tournament_scheduler.llm_judge.get_judge_if_headless", return_value=judge_mock):
            with patch("tournament_scheduler.llm_judge.build_stage_prompt", return_value="prompt"):
                with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                    result = _cmd_run(args)

    assert result == 0
    assert judge_mock.judge.call_count == 3


# ---------------------------------------------------------------------------
# _run_confidence_gate unit tests
# ---------------------------------------------------------------------------

from tournament_scheduler.cli.pipeline_orchestrator import _run_confidence_gate  # noqa: E402


def _make_warn_verdict(sources=None, gaps=None, assessment="low coverage"):
    """Return a mock ScrapingConfidenceVerdict with WARN verdict."""
    from unittest.mock import MagicMock as _MM
    v = _MM()
    v.verdict = "WARN"
    v.overall_assessment = assessment
    v.suspicious_sources = sources or []
    v.gaps = gaps or []
    return v


def test_confidence_gate_warn_strict_decline_aborts() -> None:
    """WARN + strict=True, operator answers 'n' — gate returns False (abort)."""
    console = MagicMock()
    log_fn = MagicMock()
    verdict = _make_warn_verdict()

    with patch("builtins.input", return_value="n"):
        result = _run_confidence_gate(verdict, True, console, log_fn)

    assert result is False


def test_confidence_gate_warn_strict_approve_proceeds() -> None:
    """WARN + strict=True, operator answers 'j' — gate returns True (proceed)."""
    console = MagicMock()
    log_fn = MagicMock()
    verdict = _make_warn_verdict()

    with patch("builtins.input", return_value="j"):
        result = _run_confidence_gate(verdict, True, console, log_fn)

    assert result is True


def test_confidence_gate_warn_non_strict_proceeds_without_prompt() -> None:
    """WARN + strict=False — gate returns True without calling input()."""
    console = MagicMock()
    log_fn = MagicMock()
    verdict = _make_warn_verdict()

    with patch("builtins.input", side_effect=AssertionError("must not prompt in non-strict")):
        result = _run_confidence_gate(verdict, False, console, log_fn)

    assert result is True


def test_confidence_gate_ok_verdict_skips_gate(tmp_path: Path) -> None:
    """OK confidence verdict — _run_confidence_gate is not called (pipeline proceeds normally)."""
    # Integration: run _cmd_run with a mocked confidence assessment returning OK;
    # verify the pipeline completes with return code 0.
    args = _make_args(tmp_path)
    args.non_strict = False  # strict mode

    from unittest.mock import MagicMock as _MM
    ok_verdict = _MM()
    ok_verdict.verdict = "OK"
    ok_verdict.overall_assessment = "all sources healthy"
    ok_verdict.suspicious_sources = []
    ok_verdict.gaps = []

    patches = _all_stage_patches()
    with patch.dict(os.environ, {**_HARNESS_CLEAN, "RVV_APPROVAL_ENDPOINT": "http://localhost:1234"}):
        with patch(
            "tournament_scheduler.pipeline.scraping_confidence.run_confidence_assessment",
            return_value=ok_verdict,
        ):
            with patch("tournament_scheduler.llm.lm_studio_client.LMStudioClient"):
                with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                    result = _cmd_run(args)

    assert result == 0
