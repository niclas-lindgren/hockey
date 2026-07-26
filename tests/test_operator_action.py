"""Tests for tournament_scheduler.pipeline.operator_action (issue #10)."""

from __future__ import annotations

import json

import pytest

from tournament_scheduler.pipeline.capability_result import CapabilityResult
from tournament_scheduler.pipeline.cache_manager import ScrapedDataCache
from tournament_scheduler.pipeline.operator_action import (
    DEFAULT_REGISTRY,
    ActionRegistry,
    ApprovalRequiredError,
    OperatorAction,
    RiskLevel,
    UnknownActionError,
)
from tournament_scheduler.pipeline.run_manifest import RunManifest
from tournament_scheduler.pipeline.state import PipelineState, StageName, StageStatus


class TestOperatorActionValidation:
    def test_valid_risk_level_accepted(self):
        action = OperatorAction(action_id="x", description="d", capability="c", risk_level="safe")
        assert action.risk_level == "safe"

    def test_accepts_enum_member(self):
        action = OperatorAction(action_id="x", description="d", capability="c", risk_level=RiskLevel.SAFE)
        assert action.risk_level == "safe"

    def test_invalid_risk_level_raises(self):
        with pytest.raises(ValueError):
            OperatorAction(action_id="x", description="d", capability="c", risk_level="not-a-real-level")

    @pytest.mark.parametrize("risk_level", ["destructive", "external"])
    def test_destructive_or_external_without_approval_raises(self, risk_level):
        with pytest.raises(ValueError):
            OperatorAction(
                action_id="x", description="d", capability="c", risk_level=risk_level, requires_approval=False
            )

    @pytest.mark.parametrize("risk_level", ["destructive", "external"])
    def test_destructive_or_external_with_approval_is_accepted(self, risk_level):
        action = OperatorAction(
            action_id="x", description="d", capability="c", risk_level=risk_level, requires_approval=True
        )
        assert action.requires_approval is True

    @pytest.mark.parametrize("risk_level", ["safe", "reversible"])
    def test_safe_or_reversible_do_not_require_approval_by_default(self, risk_level):
        action = OperatorAction(action_id="x", description="d", capability="c", risk_level=risk_level)
        assert action.requires_approval is False


class TestOperatorActionSerialization:
    def test_to_dict_round_trip(self):
        original = OperatorAction(
            action_id="retry_source",
            description="Retry a source",
            capability="scraping",
            arguments={"source_name": "Jar"},
            risk_level="reversible",
            requires_approval=False,
            retryable=True,
        )
        restored = OperatorAction.from_dict(original.to_dict())
        assert restored == original

    def test_to_dict_includes_schema_version(self):
        action = OperatorAction(action_id="x", description="d", capability="c")
        assert action.to_dict()["schema_version"] == 1

    def test_from_dict_ignores_unknown_fields(self):
        data = OperatorAction(action_id="x", description="d", capability="c").to_dict()
        data["some_future_field"] = "value"
        restored = OperatorAction.from_dict(data)
        assert restored.action_id == "x"

    def test_from_dict_defaults_missing_fields(self):
        restored = OperatorAction.from_dict({"action_id": "x"})
        assert restored.description == ""
        assert restored.arguments == {}
        assert restored.risk_level == "safe"

    def test_is_json_serializable(self):
        action = OperatorAction(action_id="x", description="d", capability="c", arguments={"n": 1})
        json.dumps(action.to_dict())  # raises if not serializable

    def test_with_arguments_returns_new_instance_and_merges(self):
        template = OperatorAction(action_id="x", description="d", capability="c", arguments={"a": 1})
        built = template.with_arguments(b=2)
        assert built.arguments == {"a": 1, "b": 2}
        assert template.arguments == {"a": 1}  # original untouched
        assert built is not template


class TestActionRegistryDispatch:
    def test_build_unknown_action_raises_structured_error(self):
        registry = ActionRegistry()
        with pytest.raises(UnknownActionError) as exc_info:
            registry.build("nope")
        assert exc_info.value.code == "unknown_action"
        assert exc_info.value.action_id == "nope"
        assert exc_info.value.to_dict()["code"] == "unknown_action"

    def test_execute_unknown_action_raises_structured_error(self):
        registry = ActionRegistry()
        action = OperatorAction(action_id="nope", description="d", capability="c")
        with pytest.raises(UnknownActionError):
            registry.execute(action)

    def test_execute_dispatches_to_registered_executor(self):
        registry = ActionRegistry()
        calls = []

        def executor(**kwargs):
            calls.append(kwargs)
            return CapabilityResult.ok("done")

        registry.register(OperatorAction(action_id="noop", description="d", capability="c"), executor)
        action = registry.build("noop", x=1)
        result = registry.execute(action)

        assert calls == [{"x": 1}]
        assert result.status == "ok"

    def test_execute_requires_approval_when_flagged(self):
        registry = ActionRegistry()
        registry.register(
            OperatorAction(
                action_id="risky", description="d", capability="c", risk_level="external", requires_approval=True
            ),
            lambda **kwargs: CapabilityResult.ok("done"),
        )
        action = registry.build("risky")
        with pytest.raises(ApprovalRequiredError) as exc_info:
            registry.execute(action)
        assert exc_info.value.code == "approval_required"

    def test_execute_with_approved_true_runs_the_executor(self):
        registry = ActionRegistry()
        registry.register(
            OperatorAction(
                action_id="risky", description="d", capability="c", risk_level="external", requires_approval=True
            ),
            lambda **kwargs: CapabilityResult.ok("done"),
        )
        action = registry.build("risky")
        result = registry.execute(action, approved=True)
        assert result.status == "ok"

    def test_list_actions_returns_templates(self):
        registry = ActionRegistry()
        registry.register(OperatorAction(action_id="a", description="d", capability="c"), lambda **k: None)
        registry.register(OperatorAction(action_id="b", description="d", capability="c"), lambda **k: None)
        ids = sorted(a.action_id for a in registry.list_actions())
        assert ids == ["a", "b"]

    def test_known_action_ids(self):
        registry = ActionRegistry()
        registry.register(OperatorAction(action_id="a", description="d", capability="c"), lambda **k: None)
        assert registry.known_action_ids() == ["a"]


class TestDefaultRegistryCoreActions:
    """The seven core actions the issue explicitly asks for must all be registered."""

    @pytest.mark.parametrize(
        "action_id",
        [
            "retry_source",
            "use_trusted_cache",
            "refresh_source",
            "request_credentials",
            "rerun_planning",
            "compare_candidates",
            "export_selected_plan",
            "publish_pages",
        ],
    )
    def test_core_action_is_registered(self, action_id):
        assert action_id in DEFAULT_REGISTRY.known_action_ids()

    def test_export_selected_plan_requires_approval(self):
        action = DEFAULT_REGISTRY.build("export_selected_plan", work_dir=".")
        assert action.requires_approval is True
        assert action.risk_level == "external"

    def test_publish_pages_requires_approval(self):
        action = DEFAULT_REGISTRY.build("publish_pages", work_dir=".")
        assert action.requires_approval is True
        assert action.risk_level == "external"

    def test_read_only_actions_do_not_require_approval(self):
        for action_id in ("use_trusted_cache", "compare_candidates", "request_credentials"):
            action = DEFAULT_REGISTRY.build(action_id, work_dir=".")
            assert action.requires_approval is False


class TestUseTrustedCacheExecutor:
    def test_returns_ok_with_cached_event_count(self, tmp_path):
        cache = ScrapedDataCache(work_dir=str(tmp_path))
        cache.write({"sources": {"Jar": {"name": "Jar", "event_count": 12, "scrape_timestamp": "2026-01-01T00:00:00", "events": []}}})

        action = DEFAULT_REGISTRY.build("use_trusted_cache", work_dir=str(tmp_path), source_name="Jar")
        result = DEFAULT_REGISTRY.execute(action)

        assert result.status == "ok"
        assert "12" in result.summary

    def test_returns_failed_when_no_cache_entry(self, tmp_path):
        action = DEFAULT_REGISTRY.build("use_trusted_cache", work_dir=str(tmp_path), source_name="Ghost")
        result = DEFAULT_REGISTRY.execute(action)
        assert result.status == "failed"


class TestRequestCredentialsExecutor:
    def test_raises_a_credentials_question_and_returns_blocked(self, tmp_path):
        RunManifest(tmp_path).start_run("objective")
        action = DEFAULT_REGISTRY.build(
            "request_credentials", work_dir=str(tmp_path), source_name="Kongsberg", env_vars=["KONGSBERG_USER"]
        )
        result = DEFAULT_REGISTRY.execute(action)

        assert result.status == "blocked"
        assert result.requires_human is True

        from tournament_scheduler.pipeline.escalation import unanswered_questions

        pending = unanswered_questions(str(tmp_path))
        assert len(pending) == 1
        assert pending[0]["type"] == "credentials"
        assert "KONGSBERG_USER" in pending[0]["recommendation"]

    def test_raising_twice_does_not_duplicate_the_question(self, tmp_path):
        RunManifest(tmp_path).start_run("objective")
        action = DEFAULT_REGISTRY.build("request_credentials", work_dir=str(tmp_path), source_name="Kongsberg")
        DEFAULT_REGISTRY.execute(action)
        DEFAULT_REGISTRY.execute(action)

        from tournament_scheduler.pipeline.escalation import unanswered_questions

        assert len(unanswered_questions(str(tmp_path))) == 1


class TestCompareCandidatesExecutor:
    def test_returns_warning_when_no_candidates(self, tmp_path):
        action = DEFAULT_REGISTRY.build("compare_candidates", work_dir=str(tmp_path))
        result = DEFAULT_REGISTRY.execute(action)
        assert result.status == "warning"

    def test_summarizes_recorded_candidates(self, tmp_path):
        PipelineState(tmp_path).write_stage(
            StageName.PLANNING,
            {
                "plan": {"tournaments": []},
                "candidates": [
                    {"attempt": 1, "status": "pass", "score": 90},
                    {"attempt": 2, "status": "warn", "score": 70},
                ],
                "selected_candidate_attempt": 1,
            },
            status=StageStatus.DONE,
        )
        action = DEFAULT_REGISTRY.build("compare_candidates", work_dir=str(tmp_path))
        result = DEFAULT_REGISTRY.execute(action)

        assert result.status == "ok"
        assert "2 kandidat" in result.summary
        assert len(result.evidence) == 2


class TestExportSelectedPlanExecutor:
    def test_returns_failed_when_no_plan_checkpoint(self, tmp_path):
        action = DEFAULT_REGISTRY.build("export_selected_plan", work_dir=str(tmp_path))
        result = DEFAULT_REGISTRY.execute(action, approved=True)
        assert result.status == "failed"


class TestPublishPagesExecutor:
    def test_returns_failed_when_no_export_checkpoint(self, tmp_path):
        action = DEFAULT_REGISTRY.build("publish_pages", work_dir=str(tmp_path))
        result = DEFAULT_REGISTRY.execute(action, approved=True)
        assert result.status == "failed"
        assert "eksport" in result.summary.lower()

    def test_routes_through_the_sanitizer_before_publishing(self, tmp_path):
        """A secret in the raw export must block before any git operation runs (issue #18)."""
        export_dir = tmp_path / "export"
        export_dir.mkdir()
        (export_dir / "season_plan.html").write_text(
            "<p>key=AKIAABCDEFGHIJKLMNOP</p>", encoding="utf-8"
        )
        PipelineState(tmp_path).write_stage(
            StageName.EXPORT,
            {"output_files": {"html": str(export_dir / "season_plan.html")}},
            status=StageStatus.DONE,
        )

        action = DEFAULT_REGISTRY.build(
            "publish_pages", work_dir=str(tmp_path), repo_dir=str(tmp_path)
        )
        result = DEFAULT_REGISTRY.execute(action, approved=True)

        assert result.status == "blocked"
        # No git repo exists at repo_dir — if this had reached pages_publish it
        # would have failed with a git error, not blocked with a privacy finding.
        assert not (tmp_path / ".git").exists()


class TestCapabilityResultActionsField:
    def test_defaults_to_empty_list(self):
        result = CapabilityResult.ok("done")
        assert result.actions == []

    def test_to_dict_serializes_actions(self):
        action = OperatorAction(action_id="retry_source", description="d", capability="scraping")
        result = CapabilityResult.ok("done", actions=[action])
        data = result.to_dict()
        assert data["actions"] == [action.to_dict()]

    def test_from_dict_round_trips_actions(self):
        action = OperatorAction(action_id="retry_source", description="d", capability="scraping")
        original = CapabilityResult.ok("done", actions=[action])
        restored = CapabilityResult.from_dict(original.to_dict())
        assert restored.actions == [action]

    def test_from_dict_with_no_actions_key_defaults_to_empty(self):
        restored = CapabilityResult.from_dict({"status": "ok"})
        assert restored.actions == []

    def test_suggested_actions_string_list_is_unaffected(self):
        """Existing string-based consumers must remain compatible."""
        result = CapabilityResult.ok("done", suggested_actions=["Do the thing"])
        data = result.to_dict()
        assert data["suggested_actions"] == ["Do the thing"]
        assert data["actions"] == []
