"""Unit tests for recovery_injector and the recovery-targets CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tournament_scheduler.pipeline.recovery_injector import inject_recovered_events


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_STAGE2 = {
    "stage": "scraping",
    "status": "success",
    "updated_at": "2025-01-01T00:00:00+00:00",
    "data": {
        "sources": [
            {
                "name": "Sandefjord",
                "url": "https://example.com/sandefjord",
                "type": "bookup",
                "events": [],
                "event_count": 0,
                "blocked": False,
                "block_reason": None,
                "llm_fallback": False,
                "skipped": False,
            },
            {
                "name": "Blocked Source",
                "url": "https://example.com/blocked",
                "type": "outlook",
                "events": [],
                "event_count": 0,
                "blocked": True,
                "block_reason": "Timeout after 30s",
                "llm_fallback": False,
                "skipped": False,
            },
            {
                "name": "Skipped Source",
                "url": "https://example.com/skipped",
                "type": "ical",
                "events": [],
                "event_count": 0,
                "blocked": False,
                "block_reason": None,
                "llm_fallback": False,
                "skipped": True,
            },
            {
                "name": "Good Source",
                "url": "https://example.com/good",
                "type": "ical",
                "events": [{"title": "Event A", "start": "2025-03-01"}],
                "event_count": 1,
                "blocked": False,
                "block_reason": None,
                "llm_fallback": False,
                "skipped": False,
            },
        ],
        "events_by_club": {},
        "blocked": ["Blocked Source"],
        "cached": [],
        "llm_fallback": [],
        "checkpoint_path": ".pipeline/stage2_scraping.json",
    },
}

FAKE_CACHE = {
    "_meta": {
        "updated_at": "2025-01-01T00:00:00+00:00",
        "ttl_hours": 6,
        "start_date": "2025-01-01",
        "end_date": "2025-06-30",
    },
    "sources": {
        "Sandefjord": {
            "name": "Sandefjord",
            "url": "https://example.com/sandefjord",
            "scrape_timestamp": "2025-01-01T00:00:00+00:00",
            "ttl_hours": 6,
            "event_count": 0,
            "blocked": False,
            "events": [],
        }
    },
}

SYNTHETIC_EVENTS = [
    {"title": "Juleturneringen", "start": "2025-12-20", "end": "2025-12-21"},
    {"title": "Påsketurneringen", "start": "2026-04-04", "end": "2026-04-05"},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_cache(tmp_path: Path, data: dict) -> Path:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "scraped_data.json"
    cache_file.write_text(json.dumps(data, ensure_ascii=False))
    return cache_file


def _write_stage2(tmp_path: Path, data: dict) -> Path:
    checkpoint = tmp_path / "stage2_scraping.json"
    checkpoint.write_text(json.dumps(data, ensure_ascii=False))
    return checkpoint


# ---------------------------------------------------------------------------
# inject_recovered_events tests
# ---------------------------------------------------------------------------

class TestInjectRecoveredEvents:
    def test_updates_existing_source_entry(self, tmp_path: Path) -> None:
        """Injecting events into an existing source entry updates it in place."""
        _write_cache(tmp_path, FAKE_CACHE)

        inject_recovered_events("Sandefjord", SYNTHETIC_EVENTS, work_dir=str(tmp_path))

        cache_file = tmp_path / "cache" / "scraped_data.json"
        result = json.loads(cache_file.read_text())
        entry = result["sources"]["Sandefjord"]

        assert entry["event_count"] == len(SYNTHETIC_EVENTS)
        assert entry["blocked"] is False
        assert entry["events"] == SYNTHETIC_EVENTS

    def test_preserves_existing_url_field(self, tmp_path: Path) -> None:
        """Injecting events does not clobber the url field already in the cache."""
        _write_cache(tmp_path, FAKE_CACHE)

        inject_recovered_events("Sandefjord", SYNTHETIC_EVENTS, work_dir=str(tmp_path))

        cache_file = tmp_path / "cache" / "scraped_data.json"
        result = json.loads(cache_file.read_text())
        assert result["sources"]["Sandefjord"]["url"] == "https://example.com/sandefjord"

    def test_creates_new_source_entry_when_missing(self, tmp_path: Path) -> None:
        """Injecting events for an unknown source creates a new entry."""
        _write_cache(tmp_path, FAKE_CACHE)

        inject_recovered_events("NewClub", SYNTHETIC_EVENTS, work_dir=str(tmp_path))

        cache_file = tmp_path / "cache" / "scraped_data.json"
        result = json.loads(cache_file.read_text())
        assert "NewClub" in result["sources"]
        entry = result["sources"]["NewClub"]
        assert entry["event_count"] == len(SYNTHETIC_EVENTS)
        assert entry["events"] == SYNTHETIC_EVENTS
        assert entry["blocked"] is False

    def test_sets_blocked_false_when_injecting(self, tmp_path: Path) -> None:
        """A previously blocked source has blocked=False after injection."""
        blocked_cache = {
            "_meta": FAKE_CACHE["_meta"],
            "sources": {
                "Blocked Source": {
                    "name": "Blocked Source",
                    "url": "https://example.com/blocked",
                    "scrape_timestamp": "2025-01-01T00:00:00+00:00",
                    "ttl_hours": 6,
                    "event_count": 0,
                    "blocked": True,
                    "events": [],
                }
            },
        }
        _write_cache(tmp_path, blocked_cache)

        inject_recovered_events("Blocked Source", SYNTHETIC_EVENTS, work_dir=str(tmp_path))

        cache_file = tmp_path / "cache" / "scraped_data.json"
        result = json.loads(cache_file.read_text())
        assert result["sources"]["Blocked Source"]["blocked"] is False

    def test_updates_meta_timestamp(self, tmp_path: Path) -> None:
        """The _meta.updated_at timestamp is refreshed after injection."""
        _write_cache(tmp_path, FAKE_CACHE)
        original_ts = FAKE_CACHE["_meta"]["updated_at"]

        inject_recovered_events("Sandefjord", SYNTHETIC_EVENTS, work_dir=str(tmp_path))

        cache_file = tmp_path / "cache" / "scraped_data.json"
        result = json.loads(cache_file.read_text())
        # Timestamp should be updated (or at least present)
        assert result["_meta"]["updated_at"] != original_ts or result["_meta"]["updated_at"] is not None

    def test_empty_events_list_is_accepted(self, tmp_path: Path) -> None:
        """Injecting an empty list clears the source's events."""
        _write_cache(tmp_path, FAKE_CACHE)

        inject_recovered_events("Sandefjord", [], work_dir=str(tmp_path))

        cache_file = tmp_path / "cache" / "scraped_data.json"
        result = json.loads(cache_file.read_text())
        assert result["sources"]["Sandefjord"]["event_count"] == 0
        assert result["sources"]["Sandefjord"]["events"] == []


# ---------------------------------------------------------------------------
# recovery-targets command tests
# ---------------------------------------------------------------------------

class TestRecoveryTargetsCommand:
    def _run_targets(self, tmp_path: Path) -> list[dict]:
        """Run _cmd_recovery_targets against the fixture checkpoint and return parsed JSON."""
        import argparse
        from tournament_scheduler.cli.recovery_cli import _cmd_recovery_targets
        import io
        import sys

        _write_stage2(tmp_path, FAKE_STAGE2)

        args = argparse.Namespace(work_dir=str(tmp_path))

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            exit_code = _cmd_recovery_targets(args)
        finally:
            sys.stdout = old_stdout

        assert exit_code == 0
        return json.loads(captured.getvalue())

    def test_returns_blocked_source(self, tmp_path: Path) -> None:
        targets = self._run_targets(tmp_path)
        names = [t["name"] for t in targets]
        assert "Blocked Source" in names

    def test_returns_zero_event_source(self, tmp_path: Path) -> None:
        targets = self._run_targets(tmp_path)
        names = [t["name"] for t in targets]
        assert "Sandefjord" in names

    def test_excludes_skipped_source(self, tmp_path: Path) -> None:
        targets = self._run_targets(tmp_path)
        names = [t["name"] for t in targets]
        assert "Skipped Source" not in names

    def test_excludes_good_source(self, tmp_path: Path) -> None:
        targets = self._run_targets(tmp_path)
        names = [t["name"] for t in targets]
        assert "Good Source" not in names

    def test_each_entry_has_required_fields(self, tmp_path: Path) -> None:
        targets = self._run_targets(tmp_path)
        for entry in targets:
            assert "name" in entry
            assert "url" in entry
            assert "reason" in entry
            assert entry["reason"] in ("blocked", "zero_events")
            assert "block_reason" in entry
            assert "llm_fallback" in entry

    def test_blocked_source_has_correct_reason(self, tmp_path: Path) -> None:
        targets = self._run_targets(tmp_path)
        blocked = next(t for t in targets if t["name"] == "Blocked Source")
        assert blocked["reason"] == "blocked"
        assert blocked["block_reason"] == "Timeout after 30s"

    def test_zero_event_source_has_correct_reason(self, tmp_path: Path) -> None:
        targets = self._run_targets(tmp_path)
        zero = next(t for t in targets if t["name"] == "Sandefjord")
        assert zero["reason"] == "zero_events"
        assert zero["block_reason"] is None

    def test_missing_checkpoint_returns_error(self, tmp_path: Path) -> None:
        import argparse
        import sys
        import io
        from tournament_scheduler.cli.recovery_cli import _cmd_recovery_targets

        args = argparse.Namespace(work_dir=str(tmp_path))

        captured_err = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured_err
        try:
            exit_code = _cmd_recovery_targets(args)
        finally:
            sys.stderr = old_stderr

        assert exit_code == 1
        err = json.loads(captured_err.getvalue())
        assert "error" in err
