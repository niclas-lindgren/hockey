"""Tests for the standalone activity calendar page (issues #33 and #38)."""

from __future__ import annotations

import json
from pathlib import Path

import openpyxl

from tournament_scheduler.pipeline.activity_viewer import generate_activity_artifacts, generate_html


def _write_activity_workbook(path: Path) -> None:
    wb = openpyxl.Workbook()
    wb.active.title = "Innstillinger"
    ws = wb.create_sheet("Aktiviteter")
    ws.append(["Måned", "Dato", "Aktivitet", "Sted"])
    ws.append(["Januar", 17, "Spillerutvikling JU14", "Sandefjord"])
    ws.append(["Mars", 3, "Klubbforum U13/U14", "Kongsberg"])
    wb.save(path)


class TestActivityViewer:
    def test_generate_activity_artifacts_writes_json_and_standalone_page(self, tmp_path):
        input_path = tmp_path / "input.xlsx"
        _write_activity_workbook(input_path)

        artifacts = generate_activity_artifacts(
            input_path=str(input_path),
            export_dir=str(tmp_path / "export"),
            default_year=2026,
            generated_at="2026-07-29T12:00:00Z",
        )

        assert artifacts is not None
        json_path = Path(artifacts["activities_json"])
        html_path = Path(artifacts["activities_html"])
        assert json_path.name == "activities.json"
        assert html_path.as_posix().endswith("activities/index.html")
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["activities"][0]["date"] == "2026-01-17"
        html = html_path.read_text(encoding="utf-8")
        assert "Aktivitetskalender for Region Viken Vest" in html
        assert "../activities.json" in html
        assert "SheetJS" not in html
        assert "xlsx" not in html.lower()

    def test_generate_activity_artifacts_returns_none_without_activity_sheet(self, tmp_path):
        input_path = tmp_path / "input.xlsx"
        wb = openpyxl.Workbook()
        wb.active.title = "Innstillinger"
        wb.save(input_path)

        assert generate_activity_artifacts(input_path=str(input_path), export_dir=str(tmp_path / "export")) is None

    def test_page_contains_view_switch_filters_and_accessible_details(self, tmp_path):
        html_path = Path(generate_html(export_dir=str(tmp_path / "export")))
        html = html_path.read_text(encoding="utf-8")

        assert 'body class="view-timeline"' in html
        assert "Sesongsløp" in html
        assert "Liste" in html
        assert "Årshjul" in html
        assert "Aldersgruppe" in html
        assert "Aktivitetstype" in html
        assert 'id="ageFilter"' in html
        assert 'id="typeFilter"' in html
        assert 'aria-live="polite"' in html
        assert "setAttribute('role', 'button')" in html
        assert "addEventListener('keydown'" in html
        assert "showDetails(activity)" in html
        assert "aria-label=\"${escapeHtml(formatDate(activity.date))}: ${escapeHtml(activity.title)}" in html

    def test_page_positions_timeline_and_year_wheel_markers_by_actual_date(self, tmp_path):
        html = Path(generate_html(export_dir=str(tmp_path / "export"))).read_text(encoding="utf-8")

        assert "function dayOfYear(date)" in html
        assert "function daysInYear(year)" in html
        assert "? 366 : 365" in html
        assert "function dateToPercent(iso, year)" in html
        assert "daysInYear(targetYear) - 1" in html
        assert "function dateToAngle(iso, year)" in html
        assert "Math.cos(angle)" in html
        assert "Math.sin(angle)" in html

    def test_page_derives_lanes_handles_multi_age_and_overlaps(self, tmp_path):
        html = Path(generate_html(export_dir=str(tmp_path / "export"))).read_text(encoding="utf-8")

        assert "function uniqueAgeGroups(activities)" in html
        assert "activities.flatMap(activityGroups)" in html
        assert "activityGroups(activity).forEach(group" in html
        assert "buildLaneEntries(filteredActivities, lanes)" in html
        assert "daysBetween(entry.activity.date, laneEntries[i].activity.date) > 3" in html
        assert "entry.stack = stack % 3" in html
        assert "--stack:${entry.stack}" in html

    def test_page_uses_visible_type_legend_and_non_color_cues(self, tmp_path):
        html = Path(generate_html(export_dir=str(tmp_path / "export"))).read_text(encoding="utf-8")

        assert "Forklaring av aktivitetstyper" in html
        assert "function renderLegend(types)" in html
        assert "const SHAPES = ['circle','square','diamond','ring','pill']" in html
        assert "shapeFor(type)" in html
        assert "type-cue shape-${shapeFor(key)}" in html
        assert "renderWheelShape(g, activity" in html
        assert "normalizeType(type)" in html

    def test_page_has_chronological_list_mobile_default_and_iframe_height_message(self, tmp_path):
        html = Path(generate_html(export_dir=str(tmp_path / "export"))).read_text(encoding="utf-8")

        assert "month-group" in html
        assert "activity-list" in html
        assert "matchMedia('(max-width: 760px)')" in html
        assert "mobile-default" in html
        assert "view-list" in html
        assert "rvv-activities-height" in html
        assert "postMessage" in html
        assert "overflow-x: hidden" in html
        assert "window.addEventListener('resize', announceHeight)" in html

    def test_page_filters_and_views_share_data_without_reloading(self, tmp_path):
        html = Path(generate_html(export_dir=str(tmp_path / "export"))).read_text(encoding="utf-8")

        assert "function applyFilter()" in html
        assert "const selectedAge = ageFilter.value" in html
        assert "const selectedType = typeFilter.value" in html
        assert "renderTimeline();" in html
        assert "renderWheel();" in html
        assert "renderList();" in html
        assert "timelineBtn.addEventListener('click', () => setView('timeline'))" in html
        assert "listBtn.addEventListener('click', () => setView('list'))" in html
        assert "wheelBtn.addEventListener('click', () => setView('wheel'))" in html

    def test_generate_html_output_is_deterministic_and_self_contained(self, tmp_path):
        first = Path(generate_html(export_dir=str(tmp_path / "first"))).read_text(encoding="utf-8")
        second = Path(generate_html(export_dir=str(tmp_path / "second"))).read_text(encoding="utf-8")

        assert first == second
        assert "../activities.json" in first
        assert "SheetJS" not in first
        assert "xlsx" not in first.lower()
