"""Tests for the observe-decide-act AI operator loop (issue #11)."""

from __future__ import annotations

from tournament_scheduler.pipeline.capability_result import CapabilityResult
from tournament_scheduler.pipeline.operator_action import DEFAULT_REGISTRY, ActionRegistry, OperatorAction
from tournament_scheduler.pipeline.operator_loop import (
    decide_action_for_source,
    run_source_recovery_loop,
)
from tournament_scheduler.pipeline.escalation import unanswered_questions
from tournament_scheduler.pipeline.run_manifest import RunManifest
from tournament_scheduler.pipeline.state import PipelineState, StageName, StageStatus


def _write_scraping_checkpoint(work_dir, sources: list[dict]) -> None:
    PipelineState(work_dir).write_stage(StageName.SCRAPING, {"sources": sources}, status=StageStatus.DONE)


def _blocked_source(name: str, *, reason: str = "Timeout", llm_fallback: bool = False) -> dict:
    return {
        "name": name,
        "event_count": 0,
        "blocked": True,
        "block_reason": reason,
        "llm_fallback": llm_fallback,
    }


def _healthy_source(name: str, event_count: int = 10) -> dict:
    return {"name": name, "event_count": event_count, "blocked": False, "event_expectation": {"status": "ok"}}


# ---------------------------------------------------------------------------
# Pure policy function
# ---------------------------------------------------------------------------


class TestDecideActionForSource:
    def test_ok_status_returns_no_action(self):
        health = CapabilityResult.ok("fine", capability="source_health:Jar")
        action_id, rule = decide_action_for_source(health, attempt=0, max_retries=2)
        assert action_id is None
        assert "noop" in rule

    def test_blocked_without_credentials_first_attempt_retries(self):
        health = CapabilityResult.blocked("Jar blocked", capability="source_health:Jar", problems=["timeout"])
        action_id, _rule = decide_action_for_source(health, attempt=0, max_retries=2)
        assert action_id == "retry_source"

    def test_blocked_without_credentials_second_attempt_refreshes(self):
        health = CapabilityResult.blocked("Jar blocked", capability="source_health:Jar", problems=["timeout"])
        action_id, _rule = decide_action_for_source(health, attempt=1, max_retries=2)
        assert action_id == "refresh_source"

    def test_blocked_with_credentials_requests_credentials_immediately(self):
        health = CapabilityResult.blocked(
            "Kongsberg blocked",
            capability="source_health:Kongsberg",
            suggested_actions=["Sett legitimasjon via miljøvariabler: KONGSBERG_USER"],
        )
        action_id, rule = decide_action_for_source(health, attempt=0, max_retries=2)
        assert action_id == "request_credentials"
        assert "credentials" in rule

    def test_blocked_exhausted_retries_returns_none(self):
        health = CapabilityResult.blocked("Jar blocked", capability="source_health:Jar")
        action_id, rule = decide_action_for_source(health, attempt=2, max_retries=2)
        assert action_id is None
        assert "exhausted" in rule

    def test_warning_first_attempt_refreshes(self):
        health = CapabilityResult.warning("stale", capability="source_health:Jar")
        action_id, _rule = decide_action_for_source(health, attempt=0, max_retries=2)
        assert action_id == "refresh_source"

    def test_warning_later_attempt_uses_trusted_cache(self):
        health = CapabilityResult.warning("stale", capability="source_health:Jar")
        action_id, _rule = decide_action_for_source(health, attempt=1, max_retries=2)
        assert action_id == "use_trusted_cache"


# ---------------------------------------------------------------------------
# The loop itself, against a stub registry (fast, deterministic, no network)
# ---------------------------------------------------------------------------


def _stub_registry_recovering_after_one_retry(work_dir) -> ActionRegistry:
    """retry_source: fixes the checkpoint (so the next observe() sees it as
    healthy) and reports blocked on the FIRST call, ok afterwards."""
    registry = ActionRegistry()
    call_count = {"n": 0}

    def retry_source(*, work_dir, source_name):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return CapabilityResult.blocked(f"{source_name}: still blocked", capability="source_health")
        _write_scraping_checkpoint(work_dir, [_healthy_source(source_name)])
        return CapabilityResult.ok(f"{source_name}: recovered", capability="source_health")

    registry.register(
        OperatorAction(action_id="retry_source", description="d", capability="source_health"), retry_source
    )
    registry.register(
        OperatorAction(action_id="refresh_source", description="d", capability="source_health"), retry_source
    )
    registry.register(
        OperatorAction(action_id="use_trusted_cache", description="d", capability="source_health"),
        lambda **k: CapabilityResult.ok("using cache", capability="source_health"),
    )
    registry.register(
        OperatorAction(action_id="request_credentials", description="d", capability="source_health"),
        lambda **k: CapabilityResult.blocked(
            "needs creds", capability="source_health", requires_human=True
        ),
    )
    return registry


class TestRunSourceRecoveryLoopBasics:
    def test_no_checkpoint_is_a_noop(self, tmp_path):
        summary = run_source_recovery_loop(str(tmp_path))
        assert summary == {
            "actions_taken": 0,
            "sources_resolved": [],
            "sources_escalated": [],
            "stopped_reason": "completed",
        }

    def test_all_sources_healthy_is_a_noop(self, tmp_path):
        _write_scraping_checkpoint(tmp_path, [_healthy_source("Jar"), _healthy_source("Skien")])
        summary = run_source_recovery_loop(str(tmp_path))
        assert summary["actions_taken"] == 0


class TestRunSourceRecoveryLoopRecovery:
    def test_recovers_a_blocked_source_without_human_intervention(self, tmp_path):
        """The concrete acceptance criterion: recover from at least one
        routine calendar-source failure without a human choosing commands."""
        _write_scraping_checkpoint(tmp_path, [_blocked_source("Jar")])
        registry = _stub_registry_recovering_after_one_retry(tmp_path)

        summary = run_source_recovery_loop(str(tmp_path), registry=registry)

        assert summary["sources_resolved"] == ["Jar"]
        assert summary["sources_escalated"] == []
        assert summary["actions_taken"] == 2  # first attempt (still blocked) + second (recovered)

    def test_action_log_records_target_action_rationale_policy_result_transition(self, tmp_path):
        _write_scraping_checkpoint(tmp_path, [_blocked_source("Jar")])
        registry = _stub_registry_recovering_after_one_retry(tmp_path)

        run_source_recovery_loop(str(tmp_path), registry=registry)

        log = RunManifest(tmp_path).read()["action_log"]
        assert len(log) == 2
        first, second = log
        assert first["target"] == "Jar"
        assert first["action_id"] == "retry_source"
        assert first["transition"] == "retry"
        assert first["policy_rule"]
        assert first["rationale"]
        assert first["result"]["status"] == "blocked"
        assert second["transition"] == "resolved"
        assert second["result"]["status"] == "ok"


class TestRunSourceRecoveryLoopEscalation:
    def test_credentials_required_escalates_immediately(self, tmp_path):
        """Uses the real DEFAULT_REGISTRY: the credentials path short-circuits
        on the very first observation (no retry_source call, hence no
        network need), and request_credentials' real executor is what
        actually raises the escalation question — a stub can't stand in for
        that without reimplementing it."""
        _write_scraping_checkpoint(
            tmp_path,
            [_blocked_source("Kongsberg", reason="Sett legitimasjon via miljøvariabler: KONGSBERG_USER")],
        )

        summary = run_source_recovery_loop(str(tmp_path), registry=DEFAULT_REGISTRY)

        assert summary["sources_escalated"] == ["Kongsberg"]
        assert summary["sources_resolved"] == []
        assert summary["actions_taken"] == 1
        pending = unanswered_questions(str(tmp_path))
        assert len(pending) == 1
        assert pending[0]["type"] == "credentials"

    def test_bounded_retries_then_escalates_when_never_recovers(self, tmp_path):
        _write_scraping_checkpoint(tmp_path, [_blocked_source("Jar")])
        registry = ActionRegistry()
        # Every attempt uses a distinct problem string so it never looks
        # like a no-progress repeat — this exercises the "exhausted retries"
        # path specifically, not the no-progress path.
        counter = {"n": 0}

        def always_blocked(*, work_dir, source_name):
            counter["n"] += 1
            return CapabilityResult.blocked(
                f"{source_name}: still blocked (attempt {counter['n']})", capability="source_health"
            )

        registry.register(OperatorAction(action_id="retry_source", description="d", capability="source_health"), always_blocked)
        registry.register(OperatorAction(action_id="refresh_source", description="d", capability="source_health"), always_blocked)

        summary = run_source_recovery_loop(str(tmp_path), registry=registry, max_retries_per_source=2)

        assert summary["sources_escalated"] == ["Jar"]
        assert summary["actions_taken"] == 2  # bounded: retry_source, refresh_source, then give up
        assert len(unanswered_questions(str(tmp_path))) == 1

    def test_no_progress_detection_stops_before_exhausting_retries(self, tmp_path):
        _write_scraping_checkpoint(tmp_path, [_blocked_source("Jar", reason="same reason every time")])
        registry = ActionRegistry()

        def identical_result_every_time(*, work_dir, source_name):
            return CapabilityResult.blocked(
                f"{source_name}: still blocked", capability="source_health", problems=["same reason every time"]
            )

        registry.register(
            OperatorAction(action_id="retry_source", description="d", capability="source_health"),
            identical_result_every_time,
        )
        registry.register(
            OperatorAction(action_id="refresh_source", description="d", capability="source_health"),
            identical_result_every_time,
        )

        summary = run_source_recovery_loop(str(tmp_path), registry=registry, max_retries_per_source=5)

        # Would take 5 actions to exhaust retries; no-progress detection
        # should cut it short after the second (repeated) observation.
        assert summary["actions_taken"] < 5
        assert summary["sources_escalated"] == ["Jar"]
        log = RunManifest(tmp_path).read()["action_log"]
        assert log[-1]["transition"] == "no_progress_stop"

    def test_max_actions_global_bound_stops_the_loop(self, tmp_path):
        sources = [_blocked_source(f"Source{i}") for i in range(5)]
        _write_scraping_checkpoint(tmp_path, sources)
        registry = ActionRegistry()
        registry.register(
            OperatorAction(action_id="retry_source", description="d", capability="source_health"),
            lambda **k: CapabilityResult.blocked("still blocked", capability="source_health"),
        )
        registry.register(
            OperatorAction(action_id="refresh_source", description="d", capability="source_health"),
            lambda **k: CapabilityResult.blocked("still blocked", capability="source_health"),
        )

        summary = run_source_recovery_loop(str(tmp_path), registry=registry, max_actions=3, max_retries_per_source=5)

        assert summary["actions_taken"] == 3
        assert summary["stopped_reason"] == "max_actions_reached"


class TestRunSourceRecoveryLoopResume:
    def test_resuming_after_interruption_does_not_redo_resolved_sources(self, tmp_path):
        _write_scraping_checkpoint(tmp_path, [_blocked_source("Jar")])
        registry = _stub_registry_recovering_after_one_retry(tmp_path)

        first_summary = run_source_recovery_loop(str(tmp_path), registry=registry)
        assert first_summary["sources_resolved"] == ["Jar"]

        # A second, independent invocation (simulating the process having
        # been restarted) must observe the now-healthy checkpoint and do
        # nothing further.
        second_summary = run_source_recovery_loop(str(tmp_path), registry=registry)
        assert second_summary["actions_taken"] == 0

    def test_resume_continues_with_a_still_pending_source_after_max_actions_stop(self, tmp_path):
        _write_scraping_checkpoint(tmp_path, [_blocked_source("Jar")])
        registry = _stub_registry_recovering_after_one_retry(tmp_path)

        first = run_source_recovery_loop(str(tmp_path), registry=registry, max_actions=1)
        assert first["stopped_reason"] == "max_actions_reached"
        assert first["sources_resolved"] == []

        second = run_source_recovery_loop(str(tmp_path), registry=registry)
        assert second["sources_resolved"] == ["Jar"]


class TestActionProposer:
    def test_proposer_returning_known_action_is_used(self, tmp_path):
        _write_scraping_checkpoint(tmp_path, [_blocked_source("Jar")])
        registry = _stub_registry_recovering_after_one_retry(tmp_path)

        # Propose use_trusted_cache instead of the default retry_source policy.
        proposals = []

        def proposer(health, attempt):
            proposals.append((health.status, attempt))
            return "use_trusted_cache"

        summary = run_source_recovery_loop(str(tmp_path), registry=registry, action_proposer=proposer)

        assert summary["sources_resolved"] == ["Jar"]
        assert summary["actions_taken"] == 1  # use_trusted_cache resolves immediately in the stub
        assert proposals  # the proposer was actually consulted

    def test_proposer_returning_unknown_action_falls_back_to_policy(self, tmp_path):
        _write_scraping_checkpoint(tmp_path, [_blocked_source("Jar")])
        registry = _stub_registry_recovering_after_one_retry(tmp_path)

        summary = run_source_recovery_loop(
            str(tmp_path), registry=registry, action_proposer=lambda health, attempt: "not_a_real_action"
        )

        # Falls back to the deterministic policy (retry_source), which the
        # stub resolves after one retry, same as the no-proposer case.
        assert summary["sources_resolved"] == ["Jar"]
