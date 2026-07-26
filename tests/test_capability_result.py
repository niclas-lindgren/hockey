"""Tests for tournament_scheduler.pipeline.capability_result (CapabilityResult)."""

import pytest

from tournament_scheduler.pipeline.capability_result import (
    CAPABILITY_RESULT_SCHEMA_VERSION,
    CapabilityResult,
)


class TestCapabilityResultOutcomes:
    def test_ok_result(self):
        result = CapabilityResult.ok("All good", capability="config")
        assert result.status == "ok"
        assert result.requires_human is False
        assert result.is_terminal_success is True

    def test_warning_result(self):
        result = CapabilityResult.warning("Partial data", problems=["source X blocked"])
        assert result.status == "warning"
        assert result.problems == ["source X blocked"]
        assert result.is_terminal_success is True

    def test_blocked_result_forces_requires_human(self):
        result = CapabilityResult.blocked("Need credentials for source X")
        assert result.status == "blocked"
        assert result.requires_human is True
        assert result.is_terminal_success is False

    def test_blocked_result_can_override_requires_human(self):
        result = CapabilityResult.blocked("Escalating anyway", requires_human=False)
        assert result.requires_human is False

    def test_failed_result(self):
        result = CapabilityResult.failed("Scraper crashed")
        assert result.status == "failed"
        assert result.is_terminal_success is False


class TestCapabilityResultValidation:
    def test_invalid_status_raises(self):
        with pytest.raises(ValueError):
            CapabilityResult(status="not-a-real-status")

    def test_confidence_is_clamped(self):
        assert CapabilityResult(status="ok", confidence=5.0).confidence == 1.0
        assert CapabilityResult(status="ok", confidence=-5.0).confidence == 0.0


class TestCapabilityResultSerialization:
    def test_to_dict_round_trip(self):
        original = CapabilityResult(
            status="warning",
            summary="6 sources scraped, 1 blocked",
            evidence=["source_a: 12 events", "source_b: 0 events"],
            confidence=0.8,
            artifacts=[".pipeline/stage2_scraping.json"],
            problems=["source_c blocked"],
            suggested_actions=["retry source_c"],
            requires_human=False,
            capability="scraping",
        )
        data = original.to_dict()
        restored = CapabilityResult.from_dict(data)
        assert restored == original

    def test_to_dict_includes_schema_version(self):
        data = CapabilityResult.ok("done").to_dict()
        assert data["schema_version"] == CAPABILITY_RESULT_SCHEMA_VERSION

    def test_from_dict_ignores_unknown_fields(self):
        data = CapabilityResult.ok("done", capability="export").to_dict()
        data["some_future_field"] = "value from a newer schema version"
        restored = CapabilityResult.from_dict(data)
        assert restored.status == "ok"
        assert restored.capability == "export"

    def test_from_dict_defaults_missing_fields(self):
        restored = CapabilityResult.from_dict({"status": "ok"})
        assert restored.summary == ""
        assert restored.evidence == []
        assert restored.requires_human is False

    def test_to_json_is_valid_json(self):
        import json

        parsed = json.loads(CapabilityResult.ok("done").to_json())
        assert parsed["status"] == "ok"
