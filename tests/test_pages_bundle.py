"""Tests for tournament_scheduler.pipeline.pages_bundle (issue #18)."""

from __future__ import annotations

import json
from pathlib import Path

from tournament_scheduler.pipeline.pages_bundle import (
    DEFAULT_ALLOWED_FILENAMES,
    build_public_bundle,
)


def _export_dir(tmp_path: Path) -> Path:
    d = tmp_path / "export"
    d.mkdir()
    return d


class TestDefaultAllowlist:
    def test_html_and_ics_are_included_by_default(self, tmp_path):
        export_dir = _export_dir(tmp_path)
        (export_dir / "season_plan.html").write_text("<h1>Plan</h1>", encoding="utf-8")
        (export_dir / "season_plan.ics").write_text("BEGIN:VCALENDAR\nEND:VCALENDAR\n", encoding="utf-8")

        result = build_public_bundle(str(export_dir), str(tmp_path / "public"))

        assert result.status == "ok"
        assert set(json.loads(Path((tmp_path / "pages_privacy_report.json")).read_text())["included_files"]) == {
            "season_plan.html",
            "season_plan.ics",
        }
        assert (tmp_path / "public" / "season_plan.html").exists()

    def test_never_copies_the_whole_export_directory(self, tmp_path):
        """The internal export/roster/spond/review artifacts must never be included by default."""
        export_dir = _export_dir(tmp_path)
        (export_dir / "season_plan.html").write_text("<h1>Plan</h1>", encoding="utf-8")
        (export_dir / "season_plan.xlsx").write_bytes(b"not a real workbook")
        (export_dir / "season_plan_spond_games.xlsx").write_bytes(b"not a real workbook")
        (export_dir / "season_plan.csv").write_text("club,date\n", encoding="utf-8")
        review_dir = export_dir / "review_packets"
        review_dir.mkdir()
        (review_dir / "club_a.xlsx").write_bytes(b"secret roster data")

        result = build_public_bundle(str(export_dir), str(tmp_path / "public"))

        assert result.status == "ok"
        public_files = {p.name for p in (tmp_path / "public").iterdir()}
        assert public_files == {"season_plan.html"}
        assert not (tmp_path / "public" / "review_packets").exists()

    def test_unknown_extension_is_excluded_even_if_allowlisted_by_name(self, tmp_path):
        export_dir = _export_dir(tmp_path)
        (export_dir / "season_plan.exe").write_bytes(b"MZ")

        result = build_public_bundle(
            str(export_dir), str(tmp_path / "public"), allowed_filenames={"season_plan.exe"}
        )

        assert result.status == "ok"
        assert not (tmp_path / "public" / "season_plan.exe").exists()
        report = json.loads((tmp_path / "pages_privacy_report.json").read_text())
        assert any("unknown" in e["reason"] for e in report["excluded_files"])


class TestSecretDetectionBlocksPublication:
    def test_aws_key_blocks_and_leaves_no_bundle(self, tmp_path):
        export_dir = _export_dir(tmp_path)
        (export_dir / "season_plan.html").write_text(
            "<p>key=AKIAABCDEFGHIJKLMNOP</p>", encoding="utf-8"
        )

        result = build_public_bundle(str(export_dir), str(tmp_path / "public"))

        assert result.status == "blocked"
        assert result.requires_human is True
        assert not (tmp_path / "public").exists()

    def test_bearer_url_blocks_publication(self, tmp_path):
        export_dir = _export_dir(tmp_path)
        (export_dir / "season_plan.html").write_text(
            '<a href="https://example.com/feed?access_token=abcdef123456">link</a>', encoding="utf-8"
        )

        result = build_public_bundle(str(export_dir), str(tmp_path / "public"))

        assert result.status == "blocked"

    def test_allow_findings_overrides_a_specific_false_positive(self, tmp_path):
        export_dir = _export_dir(tmp_path)
        (export_dir / "season_plan.html").write_text(
            "<p>password=placeholder-not-a-real-secret</p>", encoding="utf-8"
        )

        blocked = build_public_bundle(str(export_dir), str(tmp_path / "public"))
        assert blocked.status == "blocked"

        allowed = build_public_bundle(
            str(export_dir),
            str(tmp_path / "public"),
            allow_findings={"placeholder-not-a-real-secret"},
        )
        assert allowed.status == "ok"
        assert (tmp_path / "public" / "season_plan.html").exists()


class TestRedaction:
    def test_local_filesystem_path_is_redacted_not_blocking(self, tmp_path):
        export_dir = _export_dir(tmp_path)
        (export_dir / "season_plan.html").write_text(
            "<p>Generated from /Users/alice/hockey/input.xlsx</p>", encoding="utf-8"
        )

        result = build_public_bundle(str(export_dir), str(tmp_path / "public"))

        assert result.status == "ok"
        content = (tmp_path / "public" / "season_plan.html").read_text(encoding="utf-8")
        assert "/Users/alice" not in content
        assert "[redacted]" in content

    def test_contact_email_is_redacted(self, tmp_path):
        export_dir = _export_dir(tmp_path)
        (export_dir / "season_plan.html").write_text(
            "<p>Contact: organizer@example.com</p>", encoding="utf-8"
        )

        result = build_public_bundle(str(export_dir), str(tmp_path / "public"))

        assert result.status == "ok"
        content = (tmp_path / "public" / "season_plan.html").read_text(encoding="utf-8")
        assert "organizer@example.com" not in content

    def test_labeled_phone_number_is_redacted(self, tmp_path):
        export_dir = _export_dir(tmp_path)
        (export_dir / "season_plan.html").write_text("<p>Tlf: 123 45 678</p>", encoding="utf-8")

        result = build_public_bundle(str(export_dir), str(tmp_path / "public"))

        assert result.status == "ok"
        content = (tmp_path / "public" / "season_plan.html").read_text(encoding="utf-8")
        assert "123 45 678" not in content

    def test_ordinary_dates_and_numbers_are_not_redacted(self, tmp_path):
        """Unlabeled digit sequences (dates, scores) must survive untouched."""
        export_dir = _export_dir(tmp_path)
        original = "<p>2026-03-05 14:00 — Jar 3 - 2 Bekkelaget, hall 12345</p>"
        (export_dir / "season_plan.html").write_text(original, encoding="utf-8")

        result = build_public_bundle(str(export_dir), str(tmp_path / "public"))

        assert result.status == "ok"
        content = (tmp_path / "public" / "season_plan.html").read_text(encoding="utf-8")
        assert content == original


class TestAssetRewriting:
    def test_root_absolute_links_are_rewritten_relative(self, tmp_path):
        export_dir = _export_dir(tmp_path)
        (export_dir / "season_plan.html").write_text(
            '<link rel="stylesheet" href="/styles.css"><img src="/logo.png">', encoding="utf-8"
        )

        result = build_public_bundle(str(export_dir), str(tmp_path / "public"))

        assert result.status == "ok"
        content = (tmp_path / "public" / "season_plan.html").read_text(encoding="utf-8")
        assert 'href="styles.css"' in content
        assert 'src="logo.png"' in content

    def test_external_and_protocol_relative_links_are_untouched(self, tmp_path):
        export_dir = _export_dir(tmp_path)
        original = '<a href="https://example.com/page">x</a><script src="//cdn.example.com/a.js">'
        (export_dir / "season_plan.html").write_text(original, encoding="utf-8")

        result = build_public_bundle(str(export_dir), str(tmp_path / "public"))

        assert result.status == "ok"
        content = (tmp_path / "public" / "season_plan.html").read_text(encoding="utf-8")
        assert content == original


class TestMissingExportDir:
    def test_missing_export_dir_returns_failed(self, tmp_path):
        result = build_public_bundle(str(tmp_path / "nope"), str(tmp_path / "public"))
        assert result.status == "failed"


class TestDefaultAllowlistConstant:
    def test_default_allowlist_excludes_operational_formats(self):
        assert "season_plan.xlsx" not in DEFAULT_ALLOWED_FILENAMES
        assert "season_plan.csv" not in DEFAULT_ALLOWED_FILENAMES
        assert "season_plan_spond_games.xlsx" not in DEFAULT_ALLOWED_FILENAMES
