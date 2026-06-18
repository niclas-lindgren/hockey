"""Tests for tournament_scheduler.pipeline.stage2_scraping."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from tournament_scheduler.pipeline.cache_manager import ScrapedDataCache
from tournament_scheduler.pipeline.stage2_scraping import (
    SOURCE_GOOGLE,
    SOURCE_ICAL,
    SOURCE_OUTLOOK,
    Stage2Error,
    _events_to_dicts,
    run,
)
from tournament_scheduler.pipeline.state import PipelineState, StageName
from tournament_scheduler.models import CalendarEvent


def _make_event(name: str = "Booking") -> CalendarEvent:
    return CalendarEvent(
        date="01.01.2025",
        name=name,
        datetime=datetime(2025, 1, 1, 10, 0),
        duration_hours=2.0,
    )


def _make_config_with_sources(sources):
    return {
        "start_date": "2025-09-01",
        "end_date": "2025-12-01",
        "teams": [],
        "sources": sources,
    }


class TestRunStage2:
    def test_empty_sources_produces_done_checkpoint(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        cfg = {"start_date": "2025-09-01", "end_date": "2025-12-01", "teams": []}
        result = run(
            cfg, state,
            datetime(2025, 9, 1), datetime(2025, 12, 1),
            strict=False,
        )
        assert state.is_done(StageName.SCRAPING)
        assert result["sources"] == []

    def test_ical_source_has_no_llm_confidence(self, tmp_path):
        """iCal/Google sources do not get LLM confidence logged (informational)."""
        state = PipelineState(tmp_path / "pipeline")
        cfg = _make_config_with_sources([
            {"name": "Teamup", "type": SOURCE_ICAL, "url": "https://example.com/ical"},
        ])

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_ical_scraper",
            return_value=[_make_event()],
        ):
            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
            )

        # iCal sources should not have LLM confidence key
        src = result["sources"][0]
        assert "llm_confidence" not in src
        assert src["event_count"] == 1

    def test_zero_events_blocks_source(self, tmp_path):
        """A source returning zero events blocks the pipeline."""
        state = PipelineState(tmp_path / "pipeline")
        cfg = _make_config_with_sources([
            {"name": "HallX", "type": SOURCE_OUTLOOK, "url": "https://example.com"},
        ])

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_outlook_scraper",
            return_value=([], ""),
        ):
            with pytest.raises(Stage2Error) as exc_info:
                run(
                    cfg, state,
                    datetime(2025, 9, 1), datetime(2025, 12, 1),
                    strict=True,
                )
        assert "HallX" in str(exc_info.value)
        assert state.checkpoint_path(StageName.SCRAPING).exists()
        assert state.is_failed(StageName.SCRAPING)
        envelope = state.read_envelope(StageName.SCRAPING)
        assert envelope["status"] == "failed"
        assert envelope["data"]["blocked"] == ["HallX"]
        assert envelope["data"]["sources"][0]["name"] == "HallX"

    def test_zero_events_strict_false_does_not_raise(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        cfg = _make_config_with_sources([
            {"name": "HallY", "type": SOURCE_OUTLOOK, "url": "https://example.com"},
        ])

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_outlook_scraper",
            return_value=([], ""),
        ):
            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
                strict=False,
            )
        blocked = result.get("blocked", [])
        assert "HallY" in blocked

    def test_allow_missing_sources_keeps_partial_results(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        cfg = _make_config_with_sources([
            {
                "name": "Sandefjord Penguins",
                "type": SOURCE_OUTLOOK,
                "url": "https://www.bookup.no/Utleie/#Bug%C3%A5rdshallen___/view:item/id:4497/part:/place:3907:SANDEFJORD/q:sandefjord/r:31/mod:book",
            },
        ])

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_bookup_scraper",
            return_value=([], ""),
        ):
            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
                strict=True,
                allow_missing_sources=True,
            )

        assert state.is_done(StageName.SCRAPING)
        assert not state.is_failed(StageName.SCRAPING)
        assert result["blocked"] == ["Sandefjord Penguins"]
        assert "--allow-missing-sources" in result["warning"]
        src = result["sources"][0]
        assert "BOOKUP_EMAIL" in src["recovery_hint"]
        assert "BOOKUP_PASSWORD" in src["recovery_hint"]

    def test_outlook_source_with_events_passes(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        cfg = _make_config_with_sources([
            {"name": "Kongsberg", "type": SOURCE_OUTLOOK, "url": "https://example.com"},
        ])
        events = [_make_event("Hockey practice")]

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_outlook_scraper",
            return_value=(events, ""),
        ):
            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
            )

        assert state.is_done(StageName.SCRAPING)
        src = result["sources"][0]
        assert src["event_count"] == 1
        assert src["blocked"] is False

    def test_html_source_dispatches_to_browser_scraper(self, tmp_path):
        """'html' source type dispatches to the browser scraper (same as 'outlook')."""
        state = PipelineState(tmp_path / "pipeline")
        cfg = _make_config_with_sources([
            {"name": "OtherHall", "type": "html", "url": "https://example.com/kalender/"},
        ])
        events = [_make_event("Booking")]

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_outlook_scraper",
            return_value=(events, ""),
        ):
            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
            )

        assert state.is_done(StageName.SCRAPING)
        src = result["sources"][0]
        assert src["event_count"] == 1
        assert src["blocked"] is False
        assert src["type"] == "html"

    def test_ical_source_skipped_by_browser_scraper(self, tmp_path):
        """iCal sources do NOT use the browser scraper."""
        state = PipelineState(tmp_path / "pipeline")
        cfg = _make_config_with_sources([
            {"name": "Teamup", "type": SOURCE_ICAL, "url": "https://ics.teamup.com/feed/key"},
        ])

        with (
            patch(
                "tournament_scheduler.pipeline.stage2_scraping._run_ical_scraper",
                return_value=[_make_event("iCal event")],
            ),
            patch(
                "tournament_scheduler.pipeline.stage2_scraping._run_outlook_scraper",
            ) as mock_browser,
        ):
            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
            )

        mock_browser.assert_not_called()
        src = result["sources"][0]
        assert src["event_count"] == 1
        assert src["events"][0]["name"] == "iCal event"


class TestParallelExecution:
    """Tests for the ThreadPoolExecutor-based parallel dispatch."""

    def test_multiple_sources_all_collected(self, tmp_path):
        """All results from multiple sources are collected regardless of order."""
        state = PipelineState(tmp_path / "pipeline")
        cfg = _make_config_with_sources([
            {"name": "Kongsberg", "type": SOURCE_OUTLOOK, "url": "https://a.example.com"},
            {"name": "Skien", "type": SOURCE_ICAL, "url": "https://b.example.com"},
            {"name": "Ringerike", "type": SOURCE_ICAL, "url": "https://c.example.com"},
            {"name": "Jar", "type": SOURCE_OUTLOOK, "url": "https://d.example.com"},
        ])

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_outlook_scraper",
            return_value=([_make_event("Outlook")], "<html>"),
        ), patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_ical_scraper",
            return_value=[_make_event("iCal")],
        ):
            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
            )

        assert len(result["sources"]) == 4
        names = {s["name"] for s in result["sources"]}
        assert names == {"Kongsberg", "Skien", "Ringerike", "Jar"}
        assert sum(s["event_count"] for s in result["sources"]) == 4
        assert state.is_done(StageName.SCRAPING)

    def test_crashed_scraper_does_not_block_others(self, tmp_path):
        """A scraper that raises is caught and other sources still succeed."""
        state = PipelineState(tmp_path / "pipeline")
        cfg = _make_config_with_sources([
            {"name": "GoodSource", "type": SOURCE_ICAL, "url": "https://good.example.com"},
            {"name": "Crashy", "type": SOURCE_OUTLOOK, "url": "https://crash.example.com"},
            {"name": "AlsoGood", "type": SOURCE_ICAL, "url": "https://also.example.com"},
        ])

        original = __import__(
            "tournament_scheduler.pipeline.stage2_scraping", fromlist=["_scrape_source"]
        )._scrape_source

        call_count = {"count": 0}

        def crashing_scraper(source_cfg, *, start_date, end_date):
            call_count["count"] += 1
            if source_cfg.get("name") == "Crashy":
                raise RuntimeError("simulated crash")
            return original(source_cfg, start_date=start_date, end_date=end_date)

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_ical_scraper",
            return_value=[_make_event("iCal event")],
        ), patch(
            "tournament_scheduler.pipeline.stage2_scraping._scrape_source",
            side_effect=crashing_scraper,
        ):
            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
                strict=False,
            )

        assert len(result["sources"]) == 3
        blocked_names = result.get("blocked", [])
        assert "Crashy" in blocked_names
        # GoodSource and AlsoGood should have 1 event each
        good_events = sum(
            s["event_count"]
            for s in result["sources"]
            if s["name"] != "Crashy"
        )
        assert good_events == 2

    def test_sources_run_in_different_threads(self, tmp_path):
        """Sources dispatched via ThreadPoolExecutor use multiple OS threads."""
        import threading

        state = PipelineState(tmp_path / "pipeline")
        cfg = _make_config_with_sources([
            {"name": f"Source{i}", "type": SOURCE_ICAL, "url": f"https://s{i}.example.com"}
            for i in range(5)
        ])

        thread_ids: set[int] = set()
        call_state = {"count": 0}
        start_barrier = threading.Barrier(2)

        def record_thread(*args, **kwargs):
            call_state["count"] += 1
            thread_ids.add(threading.get_ident())
            if call_state["count"] <= 2:
                try:
                    start_barrier.wait(timeout=5)
                except threading.BrokenBarrierError as exc:
                    raise AssertionError("Expected at least two worker threads") from exc
            return [_make_event("ev")]

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_ical_scraper",
            side_effect=record_thread,
        ):
            run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
            )

        # With 5 sources and max_workers=4, at least 2 different threads must be used
        assert len(thread_ids) >= 2, f"Expected >=2 threads, got {len(thread_ids)}"


class TestUnifiedCache:
    """Stage 2 should reuse fresh unified-cache entries instead of re-scraping."""

    def _seed_cache(self, work_dir, *, start_date, end_date, source_name,
                     events, scrape_timestamp=None, blocked=False):
        cache = ScrapedDataCache(work_dir=work_dir)
        ts = scrape_timestamp or datetime.now().isoformat()
        cache.write({
            "_meta": {
                "updated_at": ts,
                "ttl_hours": 6,
                "start_date": start_date,
                "end_date": end_date,
            },
            "sources": {
                source_name: {
                    "name": source_name,
                    "url": "https://example.com",
                    "scrape_timestamp": ts,
                    "ttl_hours": 6,
                    "event_count": len(events),
                    "blocked": blocked,
                    "events": events,
                },
            },
            "source_count": 1,
            "total_events": len(events),
        })

    def test_fresh_cache_skips_scraping(self, tmp_path):
        work_dir = tmp_path / "pipeline"
        state = PipelineState(work_dir)
        cfg = _make_config_with_sources([
            {"name": "Kongsberg", "type": SOURCE_OUTLOOK, "url": "https://example.com"},
        ])
        cached_events = _events_to_dicts([_make_event("Cached practice")])
        self._seed_cache(
            work_dir,
            start_date=cfg["start_date"], end_date=cfg["end_date"],
            source_name="Kongsberg", events=cached_events,
        )

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_outlook_scraper",
        ) as mock_scraper:
            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
                strict=False,
            )

        mock_scraper.assert_not_called()
        assert result["cached"] == ["Kongsberg"]
        src = result["sources"][0]
        assert src["from_cache"] is True
        assert src["event_count"] == 1
        assert src["events"][0]["name"] == "Cached practice"

    def test_blocked_fresh_cache_is_rescraped_and_not_reused(self, tmp_path):
        work_dir = tmp_path / "pipeline"
        state = PipelineState(work_dir)
        cfg = _make_config_with_sources([
            {"name": "Kongsberg", "type": SOURCE_OUTLOOK, "url": "https://example.com"},
        ])
        cached_events = _events_to_dicts([_make_event("Cached practice")])
        self._seed_cache(
            work_dir,
            start_date=cfg["start_date"], end_date=cfg["end_date"],
            source_name="Kongsberg", events=cached_events, blocked=True,
        )

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_outlook_scraper",
            return_value=([_make_event("Fresh practice")], ""),
        ) as mock_scraper:
            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
                strict=False,
            )

        mock_scraper.assert_called_once()
        assert result["cached"] == []
        assert "from_cache" not in result["sources"][0]
        assert result["sources"][0]["events"][0]["name"] == "Fresh practice"
        cache = ScrapedDataCache(work_dir=work_dir).read()
        assert cache["sources"]["Kongsberg"]["blocked"] is False
        assert cache["sources"]["Kongsberg"]["events"][0]["name"] == "Fresh practice"

    def test_blocked_scrape_clears_previous_events_and_refreshes_timestamp(self, tmp_path):
        work_dir = tmp_path / "pipeline"
        state = PipelineState(work_dir)
        cfg = _make_config_with_sources([
            {"name": "Kongsberg", "type": SOURCE_OUTLOOK, "url": "https://example.com"},
        ])
        cached_events = _events_to_dicts([_make_event("Cached practice")])
        old_ts = (datetime.now() - timedelta(hours=12)).isoformat()
        self._seed_cache(
            work_dir,
            start_date=cfg["start_date"], end_date=cfg["end_date"],
            source_name="Kongsberg", events=cached_events,
            scrape_timestamp=old_ts,
            blocked=True,
        )

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_outlook_scraper",
            return_value=([], ""),
        ):
            run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
                strict=False,
                force_refresh=True,
            )

        cache = ScrapedDataCache(work_dir=work_dir).read()
        refreshed_ts = cache["sources"]["Kongsberg"]["scrape_timestamp"]
        assert datetime.fromisoformat(refreshed_ts) > datetime.fromisoformat(old_ts)
        assert cache["sources"]["Kongsberg"]["blocked"] is True
        assert cache["sources"]["Kongsberg"]["events"] == []

    def test_removed_source_is_pruned_from_unified_cache(self, tmp_path):
        work_dir = tmp_path / "pipeline"
        state = PipelineState(work_dir)
        cfg = _make_config_with_sources([
            {"name": "Kongsberg", "type": SOURCE_OUTLOOK, "url": "https://example.com"},
        ])
        self._seed_cache(
            work_dir,
            start_date=cfg["start_date"], end_date=cfg["end_date"],
            source_name="Kongsberg", events=_events_to_dicts([_make_event("Current")]),
        )
        cache = ScrapedDataCache(work_dir=work_dir)
        cache.write({
            **cache.read(),
            "sources": {
                "Kongsberg": cache.read()["sources"]["Kongsberg"],
                "Skien": {
                    "name": "Skien",
                    "url": "https://example.com/skien",
                    "scrape_timestamp": datetime.now().isoformat(),
                    "ttl_hours": 6,
                    "event_count": 1,
                    "blocked": False,
                    "events": _events_to_dicts([_make_event("Stale Skien")]),
                },
            },
        })

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_outlook_scraper",
        ) as mock_scraper:
            run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
                strict=False,
            )

        mock_scraper.assert_not_called()
        cache_after = ScrapedDataCache(work_dir=work_dir).read()
        assert set(cache_after["sources"].keys()) == {"Kongsberg"}

    def test_fresh_z_suffixed_timestamp_skips_scraping(self, tmp_path):
        """Cache entries written with a 'Z'-suffixed (tz-aware) timestamp,
        as the extension's ScraperAgent does, must still be recognized as
        fresh by is_stale()."""
        work_dir = tmp_path / "pipeline"
        state = PipelineState(work_dir)
        cfg = _make_config_with_sources([
            {"name": "Kongsberg", "type": SOURCE_OUTLOOK, "url": "https://example.com"},
        ])
        cached_events = _events_to_dicts([_make_event("Cached practice")])
        fresh_z = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        self._seed_cache(
            work_dir,
            start_date=cfg["start_date"], end_date=cfg["end_date"],
            source_name="Kongsberg", events=cached_events,
            scrape_timestamp=fresh_z,
        )

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_outlook_scraper",
        ) as mock_scraper:
            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
                strict=False,
            )

        mock_scraper.assert_not_called()
        assert result["cached"] == ["Kongsberg"]

    def test_stale_cache_triggers_rescrape(self, tmp_path):
        work_dir = tmp_path / "pipeline"
        state = PipelineState(work_dir)
        cfg = _make_config_with_sources([
            {"name": "Kongsberg", "type": SOURCE_OUTLOOK, "url": "https://example.com"},
        ])
        old_ts = (datetime.now() - timedelta(hours=12)).isoformat()
        self._seed_cache(
            work_dir,
            start_date=cfg["start_date"], end_date=cfg["end_date"],
            source_name="Kongsberg", events=_events_to_dicts([_make_event("Old event")]),
            scrape_timestamp=old_ts,
        )

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_outlook_scraper",
            return_value=([_make_event("Fresh event")], ""),
        ) as mock_scraper:
            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
                strict=False,
            )

        mock_scraper.assert_called_once()
        assert result["cached"] == []
        src = result["sources"][0]
        assert "from_cache" not in src
        assert src["events"][0]["name"] == "Fresh event"

    def test_force_refresh_bypasses_fresh_cache(self, tmp_path):
        work_dir = tmp_path / "pipeline"
        state = PipelineState(work_dir)
        cfg = _make_config_with_sources([
            {"name": "Kongsberg", "type": SOURCE_OUTLOOK, "url": "https://example.com"},
        ])
        self._seed_cache(
            work_dir,
            start_date=cfg["start_date"], end_date=cfg["end_date"],
            source_name="Kongsberg", events=_events_to_dicts([_make_event("Cached event")]),
        )

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_outlook_scraper",
            return_value=([_make_event("Fresh event")], ""),
        ) as mock_scraper:
            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
                strict=False, force_refresh=True,
            )

        mock_scraper.assert_called_once()
        assert result["cached"] == []
        assert result["sources"][0]["events"][0]["name"] == "Fresh event"

    def test_date_range_change_invalidates_cache(self, tmp_path):
        work_dir = tmp_path / "pipeline"
        state = PipelineState(work_dir)
        cfg = _make_config_with_sources([
            {"name": "Kongsberg", "type": SOURCE_OUTLOOK, "url": "https://example.com"},
        ])
        # Cache was built for a different season
        self._seed_cache(
            work_dir,
            start_date="2024-09-01", end_date="2024-12-01",
            source_name="Kongsberg", events=_events_to_dicts([_make_event("Old season")]),
        )

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_outlook_scraper",
            return_value=([_make_event("New season")], ""),
        ) as mock_scraper:
            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
                strict=False,
            )

        mock_scraper.assert_called_once()
        assert result["cached"] == []
        assert result["sources"][0]["events"][0]["name"] == "New season"

    def test_fresh_scrape_persisted_to_cache(self, tmp_path):
        work_dir = tmp_path / "pipeline"
        state = PipelineState(work_dir)
        cfg = _make_config_with_sources([
            {"name": "Kongsberg", "type": SOURCE_OUTLOOK, "url": "https://example.com"},
        ])

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_outlook_scraper",
            return_value=([_make_event("Practice")], ""),
        ):
            run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
                strict=False,
            )

        cache = ScrapedDataCache(work_dir=work_dir).read()
        assert cache["sources"]["Kongsberg"]["event_count"] == 1
        assert cache["sources"]["Kongsberg"]["events"][0]["name"] == "Practice"


class TestEventsToDict:
    def test_serialises_correctly(self):
        events = [_make_event("Practice")]
        dicts = _events_to_dicts(events)
        assert len(dicts) == 1
        assert dicts[0]["name"] == "Practice"
        assert dicts[0]["duration_hours"] == 2.0
        assert "datetime" in dicts[0]


class TestCheckpointDateRangeFields:
    """Stage 2 checkpoint must expose start_date, end_date, and per-source fields."""

    def test_checkpoint_has_start_and_end_date(self, tmp_path):
        """start_date and end_date must appear at the top level of the checkpoint."""
        state = PipelineState(tmp_path / "pipeline")
        cfg = _make_config_with_sources([
            {"name": "HallA", "type": SOURCE_ICAL, "url": "https://example.com/cal"},
        ])

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_ical_scraper",
            return_value=[_make_event("Booking")],
        ):
            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
                strict=False,
            )

        assert result["start_date"] == "2025-09-01", (
            f"Expected start_date='2025-09-01', got {result.get('start_date')!r}"
        )
        assert result["end_date"] == "2025-12-01", (
            f"Expected end_date='2025-12-01', got {result.get('end_date')!r}"
        )

    def test_checkpoint_sources_have_event_count_and_blocked(self, tmp_path):
        """Each source entry must include event_count and blocked fields."""
        state = PipelineState(tmp_path / "pipeline")
        cfg = _make_config_with_sources([
            {"name": "HallA", "type": SOURCE_ICAL, "url": "https://example.com/cal"},
        ])

        with patch(
            "tournament_scheduler.pipeline.stage2_scraping._run_ical_scraper",
            return_value=[_make_event("Booking"), _make_event("Cup")],
        ):
            result = run(
                cfg, state,
                datetime(2025, 9, 1), datetime(2025, 12, 1),
                strict=False,
            )

        src = result["sources"][0]
        assert "event_count" in src, "Source entry must include event_count"
        assert src["event_count"] == 2, f"Expected event_count=2, got {src['event_count']}"
        assert "blocked" in src, "Source entry must include blocked"
        assert src["blocked"] is False, "Non-blocked source must have blocked=False"

    def test_start_end_date_preserved_with_no_sources(self, tmp_path):
        """Date range fields must appear in the checkpoint even when sources list is empty."""
        state = PipelineState(tmp_path / "pipeline")
        cfg = {"start_date": "2026-01-01", "end_date": "2026-06-30", "teams": []}
        result = run(
            cfg, state,
            datetime(2026, 1, 1), datetime(2026, 6, 30),
            strict=False,
        )
        assert result["start_date"] == "2026-01-01"
        assert result["end_date"] == "2026-06-30"


class TestHarnessGate:
    """_check_stage2_checkpoint must proceed without calling any LLM."""

    def test_returns_true_when_one_source_has_events(self, tmp_path):
        """Gate must return True when at least one source has events."""
        from unittest.mock import MagicMock
        from rich.console import Console
        from tournament_scheduler.cli.pipeline_orchestrator import _check_stage2_checkpoint

        checkpoint = {
            "sources": [
                {"name": "HallA", "event_count": 5, "blocked": False},
                {"name": "HallB", "event_count": 0, "blocked": True},
            ],
            "blocked": ["HallB"],
        }
        console = Console(file=open("/dev/null", "w"))
        log_fn = MagicMock()

        result = _check_stage2_checkpoint(checkpoint, True, console, log_fn, harness_active=True)

        assert result is True

    def test_does_not_call_lm_studio_client(self, tmp_path):
        """Gate must proceed deterministically without importing or calling any LLM client."""
        from unittest.mock import MagicMock, patch
        from rich.console import Console
        from tournament_scheduler.cli.pipeline_orchestrator import _check_stage2_checkpoint

        checkpoint = {
            "sources": [{"name": "HallA", "event_count": 3, "blocked": False}],
            "blocked": [],
        }
        console = Console(file=open("/dev/null", "w"))
        log_fn = MagicMock()

        # Patch the LMStudio client to raise if it is ever instantiated
        with patch(
            "tournament_scheduler.llm_judge.get_judge_if_headless",
            side_effect=AssertionError("LLM client must not be called in gate"),
        ):
            # The gate function itself does not call get_judge_if_headless
            result = _check_stage2_checkpoint(checkpoint, True, console, log_fn, harness_active=True)

        assert result is True
