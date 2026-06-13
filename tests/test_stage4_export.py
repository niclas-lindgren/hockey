"""Tests for tournament_scheduler.pipeline.stage4_export."""

from datetime import date
from pathlib import Path
import json
import re

import openpyxl
import pytest

from tournament_scheduler.html.html_exporter import HtmlExporter
from tournament_scheduler.models import Game, Roster, SeasonPlan, Team, Tournament
from tournament_scheduler.pipeline.stage4_export import Stage4Error, _dict_to_plan, run
from tournament_scheduler.pipeline.state import PipelineState, StageName, StageStatus


def _make_plan_dict():
    """Build a minimal but valid plan checkpoint dict."""
    t1 = {
        "date": "2025-10-05",
        "arena": "Kongsberghallen",
        "age_group": "U10",
        "host_club": "Kongsberg",
        "teams": [
            {"club": "Kongsberg", "label": "Kongsberg U10A", "age_group": "U10"},
            {"club": "Skien",     "label": "Skien U10A",     "age_group": "U10"},
        ],
        "games": [
            {"home": "Kongsberg U10A", "away": "Skien U10A", "parallel_slot": 0, "round_number": 3},
        ],
        "start_time": "09:00",
    }
    return {
        "plan": {
            "start_date": "2025-09-01",
            "end_date": "2025-12-01",
            "diversity_score": 1.0,
            "pairwise_matchup_score": 1.0,
            "month_balance_score": 1.0,
            "arena_counts": {"Kongsberghallen": 1},
            "manual_adjustments": {
                "locked_dates": ["2025-10-05"],
                "banned_dates": ["2025-11-01"],
            },
            "fairness_gate": {
                "status": "pass",
                "score": 100,
                "metrics": [
                    {"label": "Kamper per lag", "value": 0, "threshold": 2, "status": "pass", "score": 100, "unit": "", "detail": "Lik kampfordeling."},
                    {"label": "Månedsbalanse", "value": 1.0, "threshold": 0.75, "status": "pass", "score": 100, "unit": "", "detail": "Jevn sesongbelastning."},
                ],
            },
            "tournaments": [t1],
        },
        "llm_confidence": 0.9,
        "llm_reasoning": "great",
        "attempts": 1,
        "llm_skipped": True,
    }


def _make_multi_age_group_plan_dict():
    data = _make_plan_dict()
    data["plan"]["tournaments"].append(
        {
            "date": "2025-11-02",
            "arena": "Bærum ishall",
            "age_group": "JU11",
            "host_club": "Jutul",
            "teams": [
                {"club": "Jutul", "label": "Jutul JU11A", "age_group": "JU11"},
                {"club": "Holmen", "label": "Holmen JU11A", "age_group": "JU11"},
            ],
            "games": [
                {"home": "Jutul JU11A", "away": "Holmen JU11A", "parallel_slot": 0, "round_number": 1},
            ],
        }
    )
    data["plan"]["arena_counts"]["Bærum ishall"] = 1
    return data


def _make_spond_plan_dict():
    data = _make_plan_dict()
    data["plan"]["tournaments"][0]["teams"] = [
        {"club": "Kongsberg", "label": "Kongsberg U10A", "age_group": "U10"},
        {"club": "Skien", "label": "Skien U10A", "age_group": "U10"},
        {"club": "Holmen", "label": "Holmen U10A", "age_group": "U10"},
    ]
    data["plan"]["tournaments"][0]["games"] = [
        {"home": "Kongsberg U10A", "away": "Skien U10A", "parallel_slot": 0, "round_number": 1},
        {"home": "Kongsberg U10A", "away": "Holmen U10A", "parallel_slot": 0, "round_number": 2},
        {"home": "Skien U10A", "away": "Holmen U10A", "parallel_slot": 0, "round_number": 3},
    ]
    return data


class TestDictToPlan:
    def test_round_trips_plan(self):
        plan_dict = _make_plan_dict()["plan"]
        plan = _dict_to_plan(plan_dict)
        assert isinstance(plan, SeasonPlan)
        assert len(plan.tournaments) == 1
        t = plan.tournaments[0]
        assert t.arena == "Kongsberghallen"
        assert t.start_time == "09:00"
        assert len(t.games) == 1
        assert t.games[0].home.label == "Kongsberg U10A"
        assert t.games[0].round_number == 3
        assert plan.manual_adjustments["locked_dates"] == ["2025-10-05"]

    def test_handles_missing_dates(self):
        plan_dict = {"tournaments": [], "diversity_score": 0.0,
                     "pairwise_matchup_score": 0.0, "month_balance_score": 0.0,
                     "arena_counts": {}}
        plan = _dict_to_plan(plan_dict)
        assert plan.start_date is None


class TestRunStage4:
    def test_produces_excel_file(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        state.write_stage(StageName.CONFIG, {"round_length_minutes": {"U10": 15}}, status=StageStatus.DONE)
        result = run(
            _make_plan_dict(), state,
            export_dir=str(tmp_path / "export"),
        )
        files = result.get("output_files", {})
        assert "excel" in files
        assert Path(files["excel"]).exists()
        workbook = openpyxl.load_workbook(files["excel"])
        overview = workbook["Sesongoversikt"]
        rows = list(overview.iter_rows(values_only=True))
        assert rows[1][7] == "09:00"
        assert rows[1][8] == "09:45"

    def test_includes_fairness_gate_sheet(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        result = run(
            _make_plan_dict(), state,
            export_dir=str(tmp_path / "export"),
        )
        files = result.get("output_files", {})
        workbook = openpyxl.load_workbook(files["excel"])
        assert "Rettferdighet" in workbook.sheetnames
        sheet = workbook["Rettferdighet"]
        rows = list(sheet.iter_rows(values_only=True))
        assert rows[0][0] == "Overordnet status"
        assert rows[2][0] == "Metrikk"
        assert rows[3][0] == "Kamper per lag"

    def test_generates_html_with_plan_driven_filters_and_ui_assets(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        result = run(
            _make_multi_age_group_plan_dict(), state,
            export_dir=str(tmp_path / "export"),
        )
        files = result.get("output_files", {})
        html_path = Path(files["html"])
        html = html_path.read_text(encoding="utf-8")

        assert '<option value="U10">U10</option>' in html
        assert '<option value="JU11">JU11</option>' in html
        assert re.search(r'Alle \((?:JU11 \+ U10|U10 \+ JU11)\)', html)
        assert 'id="themeToggle"' in html
        assert 'class="theme-toggle"' in html
        assert 'href="season_plan.xlsx"' in html
        assert 'href="season_plan.csv"' in html
        assert 'href="season_plan.ics"' in html
        assert 'href="season_plan.csv" class="export-link-btn"' in html or 'href="season_plan.csv"' in html
        assert 'Rettferdighetsgate' in html
        assert 'score-item--gate' in html
        assert 'debug-dashboard' not in html.lower()
        assert not re.search(r"[\U0001F300-\U0001FAFF]", html)

    def test_html_tournament_details_group_matches_by_round(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        result = run(
            _make_plan_dict(), state,
            export_dir=str(tmp_path / "export"),
        )
        files = result.get("output_files", {})
        html = Path(files["html"]).read_text(encoding="utf-8")

        payload = json.loads(HtmlExporter._plan_to_json(_dict_to_plan(_make_plan_dict()["plan"])))
        assert payload[0]["m"][0][3] == 3
        assert 'Kamper per runde' in html
        assert 'round-group-header' in html
        assert 'Runde ' in html

    def test_produces_ical_file(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        state.write_stage(StageName.CONFIG, {"round_length_minutes": {"U10": 15}}, status=StageStatus.DONE)
        result = run(
            _make_plan_dict(), state,
            export_dir=str(tmp_path / "export"),
        )
        files = result.get("output_files", {})
        assert "ical" in files
        ics_path = Path(files["ical"])
        assert ics_path.exists()
        assert ics_path.suffix == ".ics"
        content = ics_path.read_text()
        assert "BEGIN:VCALENDAR" in content
        assert "VEVENT" in content
        assert "DTSTART:20251005T090000Z" in content
        assert "DTEND:20251005T100000Z" in content

    def test_writes_timestamped_exports_and_flat_copies(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        result = run(
            _make_plan_dict(), state,
            export_dir=str(tmp_path / "export"),
            timestamped_export=True,
        )
        files = result.get("output_files", {})

        timestamped_paths = [Path(files[key]) for key in ("excel", "ical", "csv_games", "csv_overview", "html", "spond", "spond_games")]
        timestamp_dirs = {path.parent for path in timestamped_paths}
        assert len(timestamp_dirs) == 1
        timestamp_dir = timestamp_dirs.pop()
        assert timestamp_dir.parent == tmp_path / "export"
        assert timestamp_dir.name

        for path in timestamped_paths:
            assert path.exists()
            assert path.parent == timestamp_dir

        flat_paths = [Path(files[key]) for key in ("excel_flat", "ical_flat", "csv_games_flat", "csv_overview_flat", "html_flat", "spond_flat", "spond_games_flat")]
        for path in flat_paths:
            assert path.exists()
            assert path.parent == tmp_path / "export"

    def test_stage4_spond_export_uses_tournament_rows(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        state.write_stage(StageName.CONFIG, {"round_length_minutes": {"U10": 15}}, status=StageStatus.DONE)
        result = run(
            _make_spond_plan_dict(), state,
            export_dir=str(tmp_path / "export"),
        )
        files = result.get("output_files", {})
        workbook = openpyxl.load_workbook(files["spond"])
        sheet = workbook["Sesongplan"]
        rows = list(sheet.iter_rows(values_only=True))

        assert rows[0][0:5] == ("Dato", "Aktivitet", "Sted", "Start", "Slutt")
        assert rows[1][3] == "09:00"
        assert rows[1][4] == "09:45"
        assert rows[1][9] == "turnering"
        assert len(rows) == 2  # header + one tournament row, not one row per game

        attachment = openpyxl.load_workbook(files["spond_games"])
        assert len(attachment.sheetnames) == 1
        attachment_rows = list(attachment[attachment.sheetnames[0]].iter_rows(values_only=True))
        header_row = next(i for i, row in enumerate(attachment_rows) if row[:4] == ("Runde", "Hjemmelag", "Bortelag", "Parallellbane"))
        assert attachment_rows[header_row][0:4] == ("Runde", "Hjemmelag", "Bortelag", "Parallellbane")
        assert attachment_rows[header_row + 1][1] == "Kongsberg U10A"

    def test_produces_csv_files(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        result = run(
            _make_plan_dict(), state,
            export_dir=str(tmp_path / "export"),
        )
        files = result.get("output_files", {})
        assert "csv_games" in files
        assert "csv_overview" in files
        games_path = Path(files["csv_games"])
        assert games_path.exists()
        lines = games_path.read_text().splitlines()
        assert lines[0] == "date,arena,age_group,home,away,parallel_slot"
        assert len(lines) > 1  # header + at least one game row

    def test_marks_checkpoint_done(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        run(
            _make_plan_dict(), state,
            export_dir=str(tmp_path / "export"),
        )
        assert state.is_done(StageName.EXPORT)

    def test_raises_on_missing_plan(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        with pytest.raises(Stage4Error, match="Stage 3"):
            run({}, state, export_dir=str(tmp_path / "export"), strict=True)
