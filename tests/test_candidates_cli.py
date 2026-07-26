"""Tests for the ``rvv-miniputt candidates`` CLI command."""

from __future__ import annotations

import argparse
import json

from tournament_scheduler.cli.reporting import (
    _build_candidates_text,
    _cmd_candidates,
    _most_consequential_metric_deltas,
)
from tournament_scheduler.pipeline.state import PipelineState, StageName, StageStatus


def _write_candidates_checkpoint(work_dir, candidates: list[dict], selected_attempt: int) -> None:
    PipelineState(work_dir).write_stage(
        StageName.PLANNING,
        {
            "plan": {"fairness_gate": {"score": candidates[0]["score"]}},
            "candidates": candidates,
            "selected_candidate_attempt": selected_attempt,
        },
        status=StageStatus.DONE,
    )


def _candidate(attempt, *, seed=0, status="pass", score=90, count=4, metrics=None):
    return {
        "attempt": attempt,
        "seed": seed,
        "planner_version": "1",
        "config_fingerprint": "abc123",
        "source_fingerprint": "def456",
        "penalty_hints": {},
        "status": status,
        "score": score,
        "tournament_count": count,
        "rank": [{"pass": 2, "warn": 1, "fail": 0}[status], score, count],
        "metrics": metrics or [],
    }


class TestMostConsequentialMetricDeltas:
    def test_sorts_by_absolute_delta_descending(self):
        selected = {"metrics": [
            {"key": "a", "label": "A", "score": 90},
            {"key": "b", "label": "B", "score": 50},
        ]}
        runner_up = {"metrics": [
            {"key": "a", "label": "A", "score": 85},
            {"key": "b", "label": "B", "score": 10},
        ]}
        deltas = _most_consequential_metric_deltas(selected, runner_up)
        assert deltas[0][0] == "B"
        assert deltas[0][3] == 40
        assert deltas[1][0] == "A"

    def test_skips_metrics_with_no_delta(self):
        selected = {"metrics": [{"key": "a", "label": "A", "score": 90}]}
        runner_up = {"metrics": [{"key": "a", "label": "A", "score": 90}]}
        assert _most_consequential_metric_deltas(selected, runner_up) == []

    def test_ignores_metrics_missing_from_one_side(self):
        selected = {"metrics": [{"key": "a", "label": "A", "score": 90}, {"key": "only_selected", "label": "X", "score": 1}]}
        runner_up = {"metrics": [{"key": "a", "label": "A", "score": 80}]}
        deltas = _most_consequential_metric_deltas(selected, runner_up)
        assert [d[0] for d in deltas] == ["A"]


class TestBuildCandidatesText:
    def test_no_checkpoint_returns_helpful_message(self, tmp_path):
        text = _build_candidates_text(tmp_path)
        assert "Ingen kandidatdata" in text

    def test_lists_all_candidates_and_marks_selected(self, tmp_path):
        candidates = [_candidate(1, score=80), _candidate(2, score=95)]
        _write_candidates_checkpoint(tmp_path, candidates, selected_attempt=2)
        text = _build_candidates_text(tmp_path)
        assert "Plankandidater (2)" in text
        lines = text.splitlines()
        selected_line = next(l for l in lines if l.startswith("2 "))
        other_line = next(l for l in lines if l.startswith("1 "))
        assert "←" in selected_line
        assert "←" not in other_line

    def test_shows_metric_deltas_between_selected_and_runner_up(self, tmp_path):
        candidates = [
            _candidate(1, status="pass", score=95, metrics=[{"key": "travel", "label": "Reise", "score": 95}]),
            _candidate(2, status="pass", score=70, metrics=[{"key": "travel", "label": "Reise", "score": 40}]),
        ]
        _write_candidates_checkpoint(tmp_path, candidates, selected_attempt=1)
        text = _build_candidates_text(tmp_path)
        assert "Mest utslagsgivende forskjeller" in text
        assert "Reise" in text

    def test_includes_fingerprints(self, tmp_path):
        _write_candidates_checkpoint(tmp_path, [_candidate(1)], selected_attempt=1)
        text = _build_candidates_text(tmp_path)
        assert "Planner-versjon: 1" in text
        assert "Config-fingerprint:" in text


class TestCmdCandidates:
    def test_json_output(self, tmp_path, capsys):
        candidates = [_candidate(1, score=80), _candidate(2, score=95)]
        _write_candidates_checkpoint(tmp_path, candidates, selected_attempt=2)
        args = argparse.Namespace(work_dir=str(tmp_path), json=True)
        rc = _cmd_candidates(args)
        assert rc == 0
        printed = json.loads(capsys.readouterr().out)
        assert printed["selected_candidate_attempt"] == 2
        assert len(printed["candidates"]) == 2

    def test_human_readable_output(self, tmp_path, capsys):
        _write_candidates_checkpoint(tmp_path, [_candidate(1)], selected_attempt=1)
        args = argparse.Namespace(work_dir=str(tmp_path), json=False)
        rc = _cmd_candidates(args)
        assert rc == 0
        assert "Plankandidater" in capsys.readouterr().out

    def test_no_checkpoint_returns_0(self, tmp_path):
        args = argparse.Namespace(work_dir=str(tmp_path), json=False)
        assert _cmd_candidates(args) == 0


class TestArgParsing:
    def test_candidates_parses_defaults(self):
        from tournament_scheduler.cli.args import build_parser

        args = build_parser().parse_args(["candidates"])
        assert args.command == "candidates"
        assert args.work_dir == ".pipeline"
        assert args.json is False
