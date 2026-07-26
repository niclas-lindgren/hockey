"""Tests for the human escalation and approval protocol (pipeline/escalation.py)."""

from __future__ import annotations

import argparse
import json

import pytest

from tournament_scheduler.pipeline.capability_result import CapabilityResult
from tournament_scheduler.pipeline.escalation import (
    EscalationType,
    Question,
    answer_question,
    from_capability_result,
    infer_escalation_type,
    raise_question,
    unanswered_questions,
)
from tournament_scheduler.pipeline.run_manifest import RunManifest


class TestQuestion:
    def test_valid_type_accepted(self):
        q = Question(type="credentials", capability="scraping", summary="x")
        assert q.type == "credentials"

    def test_accepts_enum_member(self):
        q = Question(type=EscalationType.CREDENTIALS, capability="scraping", summary="x")
        assert q.type == "credentials"

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            Question(type="not-a-real-type", capability="scraping", summary="x")

    def test_id_is_stable_for_identical_fields(self):
        a = Question(type="credentials", capability="scraping", summary="Kongsberg blocked")
        b = Question(type="credentials", capability="scraping", summary="Kongsberg blocked")
        assert a.id == b.id

    def test_id_differs_for_different_summary(self):
        a = Question(type="credentials", capability="scraping", summary="Kongsberg blocked")
        b = Question(type="credentials", capability="scraping", summary="Skien blocked")
        assert a.id != b.id

    def test_to_dict_has_unanswered_shape(self):
        q = Question(
            type="incomplete_data",
            capability="scraping",
            summary="0 sources",
            context="ctx",
            alternatives=["a", "b"],
            recommendation="a",
            impact="plan cannot be trusted",
        )
        data = q.to_dict()
        assert data["answered"] is False
        assert data["answer"] is None
        assert data["alternatives"] == ["a", "b"]
        assert data["recommendation"] == "a"
        assert data["impact"] == "plan cannot be trusted"
        assert "id" in data and "created_at" in data


class TestInferEscalationType:
    def test_detects_credentials(self):
        result = CapabilityResult.blocked("x", suggested_actions=["Sett legitimasjon via ENV_VAR"])
        assert infer_escalation_type(result) == "credentials"

    def test_detects_impossible_constraints(self):
        result = CapabilityResult.blocked("x", problems=["Arena/dag-kollisjon oppdaget"])
        assert infer_escalation_type(result) == "impossible_constraints"

    def test_detects_ambiguous_policy(self):
        result = CapabilityResult.blocked("x", problems=["LLM approval gate rejected the plan"])
        assert infer_escalation_type(result) == "ambiguous_policy"

    def test_defaults_to_incomplete_data(self):
        result = CapabilityResult.blocked("x")
        assert infer_escalation_type(result) == "incomplete_data"


class TestFromCapabilityResult:
    def test_builds_question_from_result_fields(self):
        result = CapabilityResult(
            status="blocked",
            summary="Kongsberg ishall blocked",
            evidence=["event_count=0", "strategy=browser"],
            problems=["Timeout"],
            suggested_actions=["Set credentials via KONGSBERG_USER", "Try scrape-llm"],
            requires_human=True,
            capability="scraping",
        )
        question = from_capability_result(result)
        assert question.capability == "scraping"
        assert question.summary == "Kongsberg ishall blocked"
        assert question.context == "event_count=0; strategy=browser"
        assert question.alternatives == ["Set credentials via KONGSBERG_USER", "Try scrape-llm"]
        assert question.recommendation == "Set credentials via KONGSBERG_USER"
        assert question.impact == "Timeout"

    def test_explicit_escalation_type_overrides_inference(self):
        result = CapabilityResult.blocked("x", problems=["Timeout"])
        question = from_capability_result(result, escalation_type="destructive_repair")
        assert question.type == "destructive_repair"


class TestRaiseAndAnswerQuestion:
    def test_raise_records_question_in_manifest(self, tmp_path):
        RunManifest(tmp_path).start_run("objective")
        question = Question(type="credentials", capability="scraping", summary="x")
        entry = raise_question(str(tmp_path), question)
        assert entry["id"] == question.id
        assert RunManifest(tmp_path).read()["pending_questions"] == [entry]

    def test_raising_the_same_question_twice_does_not_duplicate(self, tmp_path):
        RunManifest(tmp_path).start_run("objective")
        question = Question(type="credentials", capability="scraping", summary="x")
        raise_question(str(tmp_path), question)
        raise_question(str(tmp_path), question)
        assert len(RunManifest(tmp_path).read()["pending_questions"]) == 1

    def test_answer_marks_question_answered(self, tmp_path):
        RunManifest(tmp_path).start_run("objective")
        question = Question(type="credentials", capability="scraping", summary="x")
        raise_question(str(tmp_path), question)

        entry = answer_question(str(tmp_path), question.id, "set the env var", decided_by="niclas")
        assert entry["answered"] is True
        assert entry["answer"] == "set the env var"
        assert entry["decided_by"] == "niclas"
        assert entry["decided_at"]

    def test_answer_unknown_id_raises(self, tmp_path):
        RunManifest(tmp_path).start_run("objective")
        with pytest.raises(ValueError):
            answer_question(str(tmp_path), "not-a-real-id", "answer")

    def test_unanswered_questions_excludes_answered_ones(self, tmp_path):
        RunManifest(tmp_path).start_run("objective")
        q1 = Question(type="credentials", capability="scraping", summary="q1")
        q2 = Question(type="incomplete_data", capability="planning", summary="q2")
        raise_question(str(tmp_path), q1)
        raise_question(str(tmp_path), q2)
        answer_question(str(tmp_path), q1.id, "done")

        remaining = unanswered_questions(str(tmp_path))
        assert [q["id"] for q in remaining] == [q2.id]

    def test_raising_a_question_already_answered_does_not_reopen_it(self, tmp_path):
        """The core anti-repetition guarantee: once answered, the exact same
        question raised again must stay answered, not reappear as pending."""
        RunManifest(tmp_path).start_run("objective")
        question = Question(type="credentials", capability="scraping", summary="x")
        raise_question(str(tmp_path), question)
        answer_question(str(tmp_path), question.id, "fixed it")

        raise_question(str(tmp_path), question)  # raised again by a later run

        assert unanswered_questions(str(tmp_path)) == []
        stored = RunManifest(tmp_path).read()["pending_questions"]
        assert len(stored) == 1
        assert stored[0]["answered"] is True


class TestPendingQuestionsSurviveNewRuns:
    """start_run() must carry pending_questions forward — a human answering
    a question happens *between* separate CLI invocations, so the manifest
    reset that begins every new run must not erase escalation history."""

    def test_answered_question_survives_a_new_start_run(self, tmp_path):
        manifest = RunManifest(tmp_path)
        manifest.start_run("first objective")
        question = Question(type="credentials", capability="scraping", summary="x")
        raise_question(str(tmp_path), question)
        answer_question(str(tmp_path), question.id, "fixed it")

        manifest.start_run("second objective, resumed run")

        data = manifest.read()
        assert data["objective"] == "second objective, resumed run"
        assert data["capabilities"] == []  # per-run history does reset
        assert len(data["pending_questions"]) == 1
        assert data["pending_questions"][0]["answered"] is True

    def test_unanswered_question_also_survives(self, tmp_path):
        manifest = RunManifest(tmp_path)
        manifest.start_run("first objective")
        question = Question(type="credentials", capability="scraping", summary="x")
        raise_question(str(tmp_path), question)

        manifest.start_run("second objective")

        assert len(unanswered_questions(str(tmp_path))) == 1

    def test_fresh_workspace_starts_with_no_pending_questions(self, tmp_path):
        manifest = RunManifest(tmp_path)
        data = manifest.start_run("objective")
        assert data["pending_questions"] == []


class TestOperatorEscalationIntegration:
    def test_raise_escalation_questions_scans_capabilities_requiring_human(self, tmp_path):
        from tournament_scheduler.cli.pipeline_orchestrator import _raise_escalation_questions

        manifest = RunManifest(tmp_path)
        manifest.start_run("objective")
        manifest.record_capability(
            CapabilityResult(
                status="blocked",
                summary="Kongsberg blocked",
                problems=["Timeout"],
                suggested_actions=["Set credentials via KONGSBERG_USER"],
                requires_human=True,
                capability="scraping",
            )
        )
        manifest.record_capability(CapabilityResult.ok("fine", capability="config"))

        _raise_escalation_questions(str(tmp_path))

        pending = unanswered_questions(str(tmp_path))
        assert len(pending) == 1
        assert pending[0]["capability"] == "scraping"

    def test_raise_escalation_questions_is_a_noop_when_nothing_requires_human(self, tmp_path):
        from tournament_scheduler.cli.pipeline_orchestrator import _raise_escalation_questions

        manifest = RunManifest(tmp_path)
        manifest.start_run("objective")
        manifest.record_capability(CapabilityResult.ok("fine", capability="config"))

        _raise_escalation_questions(str(tmp_path))

        assert unanswered_questions(str(tmp_path)) == []

    def test_raise_escalation_questions_never_raises_on_missing_manifest(self, tmp_path):
        from tournament_scheduler.cli.pipeline_orchestrator import _raise_escalation_questions

        _raise_escalation_questions(str(tmp_path / "does-not-exist"))  # should not raise


class TestOperatorQuestionsAndAnswerCli:
    def test_questions_json_output(self, tmp_path, capsys):
        from tournament_scheduler.cli.rvv_cli import _cmd_operator_questions

        RunManifest(tmp_path).start_run("objective")
        raise_question(str(tmp_path), Question(type="credentials", capability="scraping", summary="x"))

        args = argparse.Namespace(work_dir=str(tmp_path), json=True)
        rc = _cmd_operator_questions(args)
        assert rc == 0
        printed = json.loads(capsys.readouterr().out)
        assert len(printed) == 1
        assert printed[0]["type"] == "credentials"

    def test_questions_human_readable_shows_id_and_recommendation(self, tmp_path, capsys):
        from tournament_scheduler.cli.rvv_cli import _cmd_operator_questions

        RunManifest(tmp_path).start_run("objective")
        question = Question(
            type="credentials", capability="scraping", summary="x", recommendation="do this",
        )
        raise_question(str(tmp_path), question)

        args = argparse.Namespace(work_dir=str(tmp_path), json=False)
        rc = _cmd_operator_questions(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert question.id in out
        assert "do this" in out
        assert "(credentials)" in out

    def test_questions_empty_prints_friendly_message(self, tmp_path, capsys):
        from tournament_scheduler.cli.rvv_cli import _cmd_operator_questions

        args = argparse.Namespace(work_dir=str(tmp_path), json=False)
        rc = _cmd_operator_questions(args)
        assert rc == 0
        assert "Ingen ubesvarte" in capsys.readouterr().out

    def test_answer_records_decision_and_prints_confirmation(self, tmp_path, capsys):
        from tournament_scheduler.cli.rvv_cli import _cmd_operator_answer

        RunManifest(tmp_path).start_run("objective")
        question = Question(type="credentials", capability="scraping", summary="x")
        raise_question(str(tmp_path), question)

        args = argparse.Namespace(work_dir=str(tmp_path), question_id=question.id, answer="fixed", decided_by="niclas")
        rc = _cmd_operator_answer(args)
        assert rc == 0
        assert "Registrert svar" in capsys.readouterr().out
        assert unanswered_questions(str(tmp_path)) == []

    def test_answer_unknown_id_returns_1(self, tmp_path, capsys):
        from tournament_scheduler.cli.rvv_cli import _cmd_operator_answer

        RunManifest(tmp_path).start_run("objective")
        args = argparse.Namespace(work_dir=str(tmp_path), question_id="bogus", answer="x", decided_by=None)
        rc = _cmd_operator_answer(args)
        assert rc == 1

    def test_dispatch_routes_questions_and_answer(self):
        from unittest.mock import patch

        from tournament_scheduler.cli.rvv_cli import _cmd_operator

        with patch("tournament_scheduler.cli.rvv_cli._cmd_operator_questions", return_value=0) as mock_q:
            _cmd_operator(argparse.Namespace(operator_command="questions"))
        mock_q.assert_called_once()

        with patch("tournament_scheduler.cli.rvv_cli._cmd_operator_answer", return_value=0) as mock_a:
            _cmd_operator(argparse.Namespace(operator_command="answer"))
        mock_a.assert_called_once()


class TestArgParsing:
    def test_operator_questions_parses(self):
        from tournament_scheduler.cli.args import build_parser

        args = build_parser().parse_args(["operator", "questions"])
        assert args.operator_command == "questions"
        assert args.json is False

    def test_operator_answer_parses(self):
        from tournament_scheduler.cli.args import build_parser

        args = build_parser().parse_args(["operator", "answer", "abc123", "yes, proceed"])
        assert args.operator_command == "answer"
        assert args.question_id == "abc123"
        assert args.answer == "yes, proceed"
        assert args.decided_by is None
