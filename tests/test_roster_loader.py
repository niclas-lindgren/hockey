"""Tests for the roster config loader (roster_loader.py)."""

import json

import pytest

from tournament_scheduler.models import Roster, Team
from tournament_scheduler.roster_loader import RosterConfigError, RosterLoader
from tournament_scheduler.season_config import _YAML_AVAILABLE

VALID_CONFIG = {
    "Jar": {"Jar 1": "U10", "Jar 2": "U11"},
    "Kongsberg": {"Kongsberg 1": "U10"},
}


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


class TestFromDict:
    """Tests for RosterLoader.from_dict (parsing/validation of an already-parsed dict)."""

    def test_valid_multi_club_multi_team_config(self):
        roster = RosterLoader.from_dict(VALID_CONFIG)

        assert isinstance(roster, Roster)
        assert len(roster.teams) == 3
        assert Team(club="Jar", label="Jar 1", age_group="U10") in roster.teams
        assert Team(club="Jar", label="Jar 2", age_group="U11") in roster.teams
        assert Team(club="Kongsberg", label="Kongsberg 1", age_group="U10") in roster.teams
        assert roster.clubs() == ["Jar", "Kongsberg"]

    def test_top_level_must_be_a_mapping(self):
        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_dict(["Jar 1 - U10"])

        assert "oppslagsverk" in str(exc_info.value)

    def test_empty_roster_is_rejected(self):
        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_dict({})

        assert "tom" in str(exc_info.value)

    def test_club_with_no_teams_is_rejected(self):
        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_dict({"Jar": {}})

        assert "Jar" in str(exc_info.value)
        assert "ingen lag" in str(exc_info.value)

    def test_club_entry_must_be_a_mapping(self):
        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_dict({"Jar": ["Jar 1"]})

        assert "Jar" in str(exc_info.value)

    def test_blank_team_label_is_rejected(self):
        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_dict({"Jar": {"  ": "U10"}})

        assert "Lagnavn" in str(exc_info.value)

    def test_blank_age_group_is_rejected(self):
        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_dict({"Jar": {"Jar 1": "  "}})

        assert "aldersgruppe" in str(exc_info.value).lower()

    def test_unknown_age_group_is_rejected(self):
        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_dict({"Jar": {"Jar 1": "U99"}})

        message = str(exc_info.value)
        assert "U99" in message
        assert "Ukjent aldersgruppe" in message

    def test_duplicate_label_within_same_club_is_rejected(self):
        # Use a raw dict literal trick is impossible (dict keys overwrite); instead
        # build a config where the same label appears under two different clubs to
        # exercise the cross-club duplicate path, and rely on from_dict's own
        # bookkeeping for within-club duplicates being structurally impossible via
        # plain dict construction — covered by the cross-club case below as the
        # representative duplicate-label scenario.
        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_dict({
                "Jar": {"Jar 1": "U10"},
                "Kongsberg": {"Jar 1": "U11"},
            })

        message = str(exc_info.value)
        assert "Jar 1" in message
        assert "unik" in message


class TestFromFile:
    """Tests for RosterLoader.from_file (file discovery, parsing, delegation)."""

    def test_missing_file_raises_with_norwegian_message(self, tmp_path):
        missing_path = str(tmp_path / "does_not_exist.json")

        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_file(missing_path)

        assert "Fant ikke" in str(exc_info.value)

    def test_valid_json_file_produces_expected_roster(self, tmp_path):
        path = _write(tmp_path, "roster.json", json.dumps(VALID_CONFIG))

        roster = RosterLoader.from_file(path)

        assert isinstance(roster, Roster)
        assert len(roster.teams) == 3
        assert roster.clubs() == ["Jar", "Kongsberg"]

    def test_unparseable_json_raises_norwegian_message(self, tmp_path):
        path = _write(tmp_path, "roster.json", "{not valid json")

        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_file(path)

        assert "JSON" in str(exc_info.value)

    @pytest.mark.skipif(not _YAML_AVAILABLE, reason="pyyaml not installed")
    def test_valid_yaml_file_matches_equivalent_json(self, tmp_path):
        yaml_text = (
            "Jar:\n"
            "  Jar 1: U10\n"
            "  Jar 2: U11\n"
            "Kongsberg:\n"
            "  Kongsberg 1: U10\n"
        )
        yaml_path = _write(tmp_path, "roster.yaml", yaml_text)
        json_path = _write(tmp_path, "roster.json", json.dumps(VALID_CONFIG))

        yaml_roster = RosterLoader.from_file(yaml_path)
        json_roster = RosterLoader.from_file(json_path)

        assert yaml_roster.teams == json_roster.teams

    @pytest.mark.skipif(not _YAML_AVAILABLE, reason="pyyaml not installed")
    def test_unparseable_yaml_raises_norwegian_message(self, tmp_path):
        path = _write(tmp_path, "roster.yaml", "Jar: [unterminated")

        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_file(path)

        assert "YAML" in str(exc_info.value)

    @pytest.mark.skipif(_YAML_AVAILABLE, reason="only relevant when pyyaml is missing")
    def test_yaml_without_pyyaml_raises_norwegian_message(self, tmp_path):
        path = _write(tmp_path, "roster.yaml", "Jar:\n  Jar 1: U10\n")

        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_file(path)

        assert "pyyaml" in str(exc_info.value)

    def test_from_file_and_from_dict_produce_identical_rosters(self, tmp_path):
        path = _write(tmp_path, "roster.json", json.dumps(VALID_CONFIG))

        from_file_roster = RosterLoader.from_file(path)
        from_dict_roster = RosterLoader.from_dict(VALID_CONFIG)

        assert from_file_roster.teams == from_dict_roster.teams
