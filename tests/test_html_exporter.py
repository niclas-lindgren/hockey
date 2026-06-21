"""Tests asserting that the consolidated hero section is correct after
removing the separate 'Min ærlige dom' judgment section."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tournament_scheduler.html.html_exporter import HtmlExporter
from tournament_scheduler.models import Game, SeasonPlan, Team, Tournament
from tournament_scheduler.pipeline.stage4_export import _dict_to_plan


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_minimal_plan() -> SeasonPlan:
    """Return a minimal SeasonPlan with one U10 tournament."""
    plan_dict = {
        "start_date": "2025-10-01",
        "end_date": "2025-12-01",
        "diversity_score": 1.0,
        "pairwise_matchup_score": 1.0,
        "month_balance_score": 1.0,
        "arena_counts": {"Kongsberghallen": 1},
        "fairness_gate": {
            "status": "pass",
            "score": 100,
            "metrics": [
                {
                    "label": "Kamper per lag",
                    "value": 0,
                    "threshold": 2,
                    "status": "pass",
                    "score": 100,
                    "unit": "",
                    "detail": "Lik kampfordeling.",
                },
            ],
        },
        "tournaments": [
            {
                "date": "2025-10-05",
                "arena": "Kongsberghallen",
                "age_group": "U10",
                "host_club": "Kongsberg",
                "teams": [
                    {"club": "Kongsberg", "label": "Kongsberg U10A", "age_group": "U10"},
                    {"club": "Skien", "label": "Skien U10A", "age_group": "U10"},
                ],
                "games": [
                    {
                        "home": "Kongsberg U10A",
                        "away": "Skien U10A",
                        "parallel_slot": 0,
                        "round_number": 1,
                    }
                ],
                "start_time": "09:00",
            }
        ],
    }
    return _dict_to_plan(plan_dict)


def _export_report_html(tmp_path: Path) -> str:
    """Export a minimal plan and return the report HTML string."""
    plan = _make_minimal_plan()
    exporter = HtmlExporter()
    out_path = tmp_path / "season_plan.html"
    exporter.export(plan, out_path, age_groups=["U10"])
    report_path = tmp_path / "season_plan_report.html"
    return report_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestNoJudgmentSection:
    """The separate 'Min ærlige dom' section must not appear in the report."""

    def test_old_section_heading_absent(self, tmp_path):
        html = _export_report_html(tmp_path)
        assert "Min ærlige dom" not in html, (
            "The old judgment section heading should not appear in the report HTML"
        )

    def test_old_section_id_absent(self, tmp_path):
        html = _export_report_html(tmp_path)
        assert 'id="opinionatedJudgment"' not in html, (
            "The old opinionatedJudgment section id should not appear in the report HTML"
        )

    def test_report_judgment_placeholder_not_in_output(self, tmp_path):
        html = _export_report_html(tmp_path)
        assert "$REPORT_JUDGMENT$" not in html, (
            "$REPORT_JUDGMENT$ placeholder should be fully substituted or removed"
        )


class TestHeroStatusFromJudgmentTone:
    """Hero section status class must be derived from judgment tone, not fairness_gate."""

    def test_hero_class_contains_pass_for_strong_plan(self, tmp_path):
        """A plan with high scores should yield tone 'strong' -> status 'pass'."""
        html = _export_report_html(tmp_path)
        # The hero div uses report-hero--<status>
        assert 'report-hero--pass' in html, (
            "Hero div should carry report-hero--pass class for a high-quality plan"
        )

    def test_hero_tone_label_not_fairness_gate_label(self, tmp_path):
        html = _export_report_html(tmp_path)
        # Tone labels from judgment: SOLID / BLANDET / IKKE KLAR
        # Old fairness-gate labels: KLAR FOR GJENNOMGANG / MÅ SJEKKES / KREVER ENDRING
        assert "SOLID" in html or "BLANDET" in html or "IKKE KLAR" in html, (
            "Hero should display a judgment tone label (SOLID/BLANDET/IKKE KLAR)"
        )


class TestJudgmentCardsInHero:
    """The 4 judgment detail cards must appear inside the hero section."""

    CARD_LABELS = ["Matchup", "Belastning", "Hjemmeturneringer", "Reise"]

    def test_all_card_labels_present(self, tmp_path):
        html = _export_report_html(tmp_path)
        for label in self.CARD_LABELS:
            assert label in html, f"Judgment card label '{label}' not found in report HTML"

    def test_cards_appear_inside_hero_section(self, tmp_path):
        html = _export_report_html(tmp_path)
        # Hero section starts with report-overview and ends before the first other section
        hero_match = re.search(
            r'<div class="report-hero[^"]*">(.*?)</div>\s*<span class="report-status-pill',
            html,
            re.DOTALL,
        )
        assert hero_match is not None, "Could not locate hero section in report HTML"
        hero_html = hero_match.group(1)
        for label in self.CARD_LABELS:
            assert label in hero_html, (
                f"Judgment card label '{label}' should be inside the hero section"
            )
