"""Tests for the roster config loader (roster_loader.py)."""

import json

import pytest

from tournament_scheduler.models import Roster, Team
from tournament_scheduler.roster_loader import RosterConfigError, RosterLoader
from tournament_scheduler.season_config import _YAML_AVAILABLE

VALID_CONFIG = {
    "Jar": {"U10": ["Jar 1", "Jar 2"], "U11": ["Jar 1"]},
    "Kongsberg": {"U10": ["Kongsberg 1"]},
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
        assert len(roster.teams) == 4
        assert Team(club="Jar", label="Jar 1", age_group="U10") in roster.teams
        assert Team(club="Jar", label="Jar 2", age_group="U10") in roster.teams
        assert Team(club="Jar", label="Jar 1", age_group="U11") in roster.teams
        assert Team(club="Kongsberg", label="Kongsberg 1", age_group="U10") in roster.teams
        assert roster.clubs() == ["Jar", "Kongsberg"]

    def test_same_label_in_different_age_groups_is_allowed(self):
        config = {"Sandefjord": {"U10": ["Sandefjord 1"], "U11": ["Sandefjord 1"]}}
        roster = RosterLoader.from_dict(config)

        assert len(roster.teams) == 2
        assert Team(club="Sandefjord", label="Sandefjord 1", age_group="U10") in roster.teams
        assert Team(club="Sandefjord", label="Sandefjord 1", age_group="U11") in roster.teams

    def test_top_level_must_be_a_mapping(self):
        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_dict(["Jar 1 - U10"])

        assert "oppslagsverk" in str(exc_info.value)

    def test_empty_roster_is_rejected(self):
        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_dict({})

        assert "tom" in str(exc_info.value)

    def test_club_with_no_age_groups_is_rejected(self):
        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_dict({"Jar": {}})

        assert "Jar" in str(exc_info.value)
        assert "ingen lag" in str(exc_info.value)

    def test_club_entry_must_be_a_mapping(self):
        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_dict({"Jar": ["U10"]})

        assert "Jar" in str(exc_info.value)

    def test_age_group_value_must_be_a_list(self):
        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_dict({"Jar": {"U10": "Jar 1"}})

        assert "Jar" in str(exc_info.value)

    def test_empty_label_list_is_rejected(self):
        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_dict({"Jar": {"U10": []}})

        assert "Jar" in str(exc_info.value)

    def test_blank_team_label_is_rejected(self):
        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_dict({"Jar": {"U10": ["  "]}})

        assert "Lagnavn" in str(exc_info.value)

    def test_blank_age_group_is_rejected(self):
        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_dict({"Jar": {"  ": ["Jar 1"]}})

        assert "aldersgruppe" in str(exc_info.value).lower()

    def test_unknown_age_group_is_rejected(self):
        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_dict({"Jar": {"U99": ["Jar 1"]}})

        message = str(exc_info.value)
        assert "U99" in message
        assert "Ukjent aldersgruppe" in message

    def test_duplicate_label_within_same_club_and_age_group_is_rejected(self):
        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_dict({"Jar": {"U10": ["Jar 1", "Jar 1"]}})

        message = str(exc_info.value)
        assert "Jar 1" in message
        assert "unik" in message


class TestNeighborClubs:
    """Tests for the neighborClubs section added in cross-region expansion."""

    def test_extended_format_with_neighbor_clubs(self):
        config = {
            "federationDefaults": {"parallelGames": {}},
            "clubs": {
                "Jar": {"JU10": ["Jar 1"]},
                "Kongsberg": {"JU10": ["Kongsberg 1"]},
            },
            "neighborClubs": {
                "Oslo": {"JU10": ["Oslo 1", "Oslo 2"]},
                "Furuset": {"JU10": ["Furuset JU10"]},
            },
        }

        roster = RosterLoader.from_dict(config)

        assert len(roster.teams) == 5

        # RVV clubs have region="RVV"
        jar_team = Team(club="Jar", label="Jar 1", age_group="JU10", region="RVV")
        kongsberg_team = Team(club="Kongsberg", label="Kongsberg 1", age_group="JU10", region="RVV")
        assert jar_team in roster.teams
        assert kongsberg_team in roster.teams

        # Neighbor clubs have region set to their club name
        oslo_1 = Team(club="Oslo", label="Oslo 1", age_group="JU10", region="Oslo")
        oslo_2 = Team(club="Oslo", label="Oslo 2", age_group="JU10", region="Oslo")
        furuset = Team(club="Furuset", label="Furuset JU10", age_group="JU10", region="Furuset")
        assert oslo_1 in roster.teams
        assert oslo_2 in roster.teams
        assert furuset in roster.teams

    def test_extended_format_without_neighbor_clubs_is_unchanged(self):
        config = {
            "federationDefaults": {"parallelGames": {}},
            "clubs": {
                "Jar": {"JU10": ["Jar 1"]},
            },
        }

        roster = RosterLoader.from_dict(config)

        assert len(roster.teams) == 1
        assert roster.teams[0].region == "RVV"

    def test_empty_neighbor_clubs_is_ignored(self):
        config = {
            "clubs": {
                "Jar": {"JU10": ["Jar 1"]},
            },
            "neighborClubs": {},
        }

        roster = RosterLoader.from_dict(config)

        assert len(roster.teams) == 1
        assert roster.teams[0].region == "RVV"

    def test_flat_format_ignores_neighbor_clubs_silently(self):
        """Flat format (no 'clubs' key) does not process neighborClubs."""
        config = {
            "Jar": {"JU10": ["Jar 1"]},
            "neighborClubs": {
                "Oslo": {"JU10": ["Oslo 1"]},
            },
        }

        # Flat format treats all top-level keys as club entries, so
        # "neighborClubs" would be parsed as a club name and rejected
        # because its value is a dict with "JU10" -> list, not a mapping
        # of age group -> list.
        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_dict(config)

        assert "neighborClubs" in str(exc_info.value)

    def test_neighbor_clubs_invalid_age_group(self):
        config = {
            "clubs": {
                "Jar": {"JU10": ["Jar 1"]},
            },
            "neighborClubs": {
                "Oslo": {"U99": ["Oslo 1"]},
            },
        }

        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_dict(config)

        assert "U99" in str(exc_info.value)

    def test_neighbor_clubs_empty_entry_is_rejected(self):
        config = {
            "clubs": {
                "Jar": {"JU10": ["Jar 1"]},
            },
            "neighborClubs": {
                "Oslo": {},
            },
        }

        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_dict(config)

        assert "Oslo" in str(exc_info.value)
        assert "ingen lag" in str(exc_info.value).lower()

    def test_neighbor_clubs_not_a_dict_is_rejected(self):
        config = {
            "clubs": {
                "Jar": {"JU10": ["Jar 1"]},
            },
            "neighborClubs": "bare en streng",
        }

        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_dict(config)

        assert "neighborClubs" in str(exc_info.value)
        assert "oppslagsverk" in str(exc_info.value)


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
        assert len(roster.teams) == 4
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
            "  U10:\n"
            "    - Jar 1\n"
            "    - Jar 2\n"
            "  U11:\n"
            "    - Jar 1\n"
            "Kongsberg:\n"
            "  U10:\n"
            "    - Kongsberg 1\n"
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
        path = _write(tmp_path, "roster.yaml", "Jar:\n  U10:\n    - Jar 1\n")

        with pytest.raises(RosterConfigError) as exc_info:
            RosterLoader.from_file(path)

        assert "pyyaml" in str(exc_info.value)

    def test_from_file_and_from_dict_produce_identical_rosters(self, tmp_path):
        path = _write(tmp_path, "roster.json", json.dumps(VALID_CONFIG))

        from_file_roster = RosterLoader.from_file(path)
        from_dict_roster = RosterLoader.from_dict(VALID_CONFIG)

        assert from_file_roster.teams == from_dict_roster.teams
