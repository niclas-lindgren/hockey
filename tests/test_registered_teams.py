"""Tests for SharePoint registered-team CSV validation and payloads."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tournament_scheduler.pipeline.registered_teams import (
    RegisteredTeamsValidationError,
    build_registered_teams_payload,
)


def _csv(path: Path, content: str, *, encoding: str = "utf-8") -> Path:
    path.write_text(content, encoding=encoding)
    return path


class TestRegisteredTeamsPayload:
    def test_header_only_csv_is_valid_empty_payload(self, tmp_path):
        payload, report = build_registered_teams_payload(
            _csv(tmp_path / "teams.csv", "club,label,age_group\n"),
            generated_at="2026-07-30T12:00:00Z",
        )

        assert payload == {
            "schema_version": 1,
            "generated_at": "2026-07-30T12:00:00Z",
            "title": "Påmeldte lag",
            "total_teams": 0,
            "total_clubs": 0,
            "age_groups": [],
        }
        assert report["error_count"] == 0
        assert report["row_count"] == 0

    def test_groups_by_configured_age_group_then_club_and_team(self, tmp_path):
        config = tmp_path / "input.json"
        config.write_text(json.dumps({"age_groups": ["U8", "U10", "JU10"]}), encoding="utf-8")
        path = _csv(
            tmp_path / "teams.csv",
            "club,label,age_group\n"
            "Jar,Jar 2,U10\n"
            "Kongsberg,Kongsberg,U8\n"
            "Jar,Jar 1,U10\n"
            "Frisk Asker,Frisk JU10,JU10\n",
        )

        payload, _report = build_registered_teams_payload(
            path,
            config_path=config,
            generated_at="2026-07-30T12:00:00Z",
        )

        assert payload["total_teams"] == 4
        assert payload["total_clubs"] == 3
        assert [entry["age_group"] for entry in payload["age_groups"]] == ["U8", "U10", "JU10"]
        u10 = payload["age_groups"][1]
        assert u10["team_count"] == 2
        assert u10["clubs"] == [{"club": "Jar", "team_count": 2, "teams": ["Jar 1", "Jar 2"]}]

    def test_normalizes_utf8_bom_and_whitespace(self, tmp_path):
        path = tmp_path / "teams.csv"
        path.write_bytes("\ufeffclub,label,age_group\n Jar , Jar   1 , U10 \n".encode("utf-8"))

        payload, report = build_registered_teams_payload(path)

        assert payload["age_groups"][0]["clubs"][0] == {"club": "Jar", "team_count": 1, "teams": ["Jar 1"]}
        assert report["included_columns"] == ["club", "label", "age_group"]

    def test_reports_extra_private_columns_but_excludes_them_from_public_payload(self, tmp_path):
        path = _csv(
            tmp_path / "teams.csv",
            "club,label,age_group,email,SharePointId,comments\n"
            "Jar,Jar 1,U10,person@example.com,42,secret note\n",
        )

        payload, report = build_registered_teams_payload(path)
        public_text = json.dumps(payload, ensure_ascii=False)

        assert sorted(report["excluded_columns"]) == ["SharePointId", "comments", "email"]
        assert "person@example.com" not in public_text
        assert "secret note" not in public_text
        assert "42" not in public_text
        assert "Kun club, label og age_group" in report["privacy_note"]

    def test_rejects_missing_required_columns(self, tmp_path):
        with pytest.raises(RegisteredTeamsValidationError) as excinfo:
            build_registered_teams_payload(_csv(tmp_path / "teams.csv", "club,label\nJar,Jar 1\n"))

        assert "Mangler påkrevd kolonne: age_group" in excinfo.value.errors
        assert excinfo.value.report["error_count"] == 1

    def test_rejects_blank_fields_with_row_numbers(self, tmp_path):
        with pytest.raises(RegisteredTeamsValidationError) as excinfo:
            build_registered_teams_payload(
                _csv(tmp_path / "teams.csv", "club,label,age_group\nJar,,U10\n,Holmen 1,U10\n")
            )

        assert "Rad 2: 'label' mangler verdi." in excinfo.value.errors
        assert "Rad 3: 'club' mangler verdi." in excinfo.value.errors

    def test_rejects_duplicate_normalized_rows(self, tmp_path):
        with pytest.raises(RegisteredTeamsValidationError) as excinfo:
            build_registered_teams_payload(
                _csv(tmp_path / "teams.csv", "club,label,age_group\nJar,Jar 1,U10\n jar , JAR   1 , u10\n")
            )

        assert any("duplikat av rad 2" in error for error in excinfo.value.errors)

    def test_validates_age_groups_when_config_is_available(self, tmp_path):
        config = tmp_path / "input.json"
        config.write_text(json.dumps({"age_groups": ["U8", "U10"]}), encoding="utf-8")

        with pytest.raises(RegisteredTeamsValidationError) as excinfo:
            build_registered_teams_payload(
                _csv(tmp_path / "teams.csv", "club,label,age_group\nJar,Jar JU10,JU10\n"),
                config_path=config,
            )

        assert "Rad 2: aldersgruppen 'JU10' finnes ikke" in excinfo.value.errors[0]

    def test_source_fingerprint_is_private_validation_metadata(self, tmp_path):
        payload, report = build_registered_teams_payload(_csv(tmp_path / "teams.csv", "club,label,age_group\n"))

        assert len(report["source_sha256"]) == 64
        assert "source_sha256" not in payload
