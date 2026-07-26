"""Tests for the previous_sources history rotation in ScrapedDataCache.build_from_checkpoint."""

from __future__ import annotations

from tournament_scheduler.pipeline.cache_manager import ScrapedDataCache


def _scraping_result(event_count: int) -> dict:
    # ScrapedDataCache derives event_count from len(events), not from a
    # separately-passed event_count field.
    events = [{"date": f"2026-09-{i:02d}", "name": f"Kamp {i}"} for i in range(1, event_count + 1)]
    return {
        "sources": [
            {"name": "Jar", "url": "https://jar.example", "type": "ical", "blocked": False, "events": events},
        ]
    }


class TestPreviousSourcesRotation:
    def test_first_build_has_no_previous_sources(self, tmp_path):
        cache = ScrapedDataCache(work_dir=str(tmp_path))
        data = cache.build_from_checkpoint({"sources": []}, _scraping_result(5))
        assert data["previous_sources"] == {}
        assert data["sources"]["Jar"]["event_count"] == 5

    def test_second_build_rotates_first_generation_into_previous(self, tmp_path):
        cache = ScrapedDataCache(work_dir=str(tmp_path))
        cache.build_from_checkpoint({"sources": []}, _scraping_result(5))
        data = cache.build_from_checkpoint({"sources": []}, _scraping_result(9))

        assert data["sources"]["Jar"]["event_count"] == 9
        assert data["previous_sources"]["Jar"]["event_count"] == 5

    def test_only_one_generation_of_history_is_retained(self, tmp_path):
        cache = ScrapedDataCache(work_dir=str(tmp_path))
        cache.build_from_checkpoint({"sources": []}, _scraping_result(1))
        cache.build_from_checkpoint({"sources": []}, _scraping_result(2))
        data = cache.build_from_checkpoint({"sources": []}, _scraping_result(3))

        assert data["sources"]["Jar"]["event_count"] == 3
        assert data["previous_sources"]["Jar"]["event_count"] == 2
