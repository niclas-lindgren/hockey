"""Tests for tournament_scheduler.season_config — federation parallel-games defaults."""

from unittest.mock import patch

import pytest

from tournament_scheduler.season_config import (
    FEDERATION_PARALLEL_GAMES_DEFAULTS,
    KNOWN_AGE_GROUPS,
    ParallelGamesConfig,
    SeasonConfigError,
)


class TestFederationDefaults:
    """ParallelGamesConfig uses FEDERATION_PARALLEL_GAMES_DEFAULTS as fallback."""

    def test_empty_config_returns_federation_defaults_for_all_age_groups(self):
        """from_dict({}) should return federation default for every known age group."""
        config = ParallelGamesConfig.from_dict({})
        for age_group, expected in FEDERATION_PARALLEL_GAMES_DEFAULTS.items():
            assert config.parallel_games_for(age_group) == expected, (
                f"{age_group}: expected {expected}, got {config.parallel_games_for(age_group)}"
            )

    def test_settings_for_unconfigured_age_group_uses_federation_default(self):
        """settings_for returns AgeGroupSettings with the per-age-group federation default."""
        config = ParallelGamesConfig.from_dict({})
        for age_group, expected in FEDERATION_PARALLEL_GAMES_DEFAULTS.items():
            settings = config.settings_for(age_group)
            assert settings.parallel_games == expected

    def test_ju12_and_u12_federation_default_is_2(self):
        """Confirmed federation rules: JU12 and U12 max parallel games = 2."""
        assert FEDERATION_PARALLEL_GAMES_DEFAULTS["JU12"] == 2
        assert FEDERATION_PARALLEL_GAMES_DEFAULTS["U12"] == 2

    def test_all_known_age_groups_have_a_federation_default(self):
        """Every entry in KNOWN_AGE_GROUPS must have a federation default."""
        assert set(FEDERATION_PARALLEL_GAMES_DEFAULTS.keys()) == KNOWN_AGE_GROUPS

    def test_configured_value_within_limit_returns_configured_value(self):
        """When parallelGames <= federation max, the configured value is used as-is."""
        config = ParallelGamesConfig.from_dict({"JU12": 1})
        assert config.parallel_games_for("JU12") == 1

    def test_configured_value_at_exact_limit_returns_configured_value(self):
        """A value exactly equal to the federation max should not change."""
        fed_max = FEDERATION_PARALLEL_GAMES_DEFAULTS["U10"]
        config = ParallelGamesConfig.from_dict({"U10": fed_max})
        assert config.parallel_games_for("U10") == fed_max


class TestFederationViolationWarning:
    """Warning is emitted when configured parallelGames exceeds federation limit."""

    def test_exceeding_ju12_limit_triggers_print_warning(self):
        """Config with JU12: 3 (limit 2) should trigger print_warning with JU12 and limit."""
        called_messages = []

        def capture_warning(msg):
            called_messages.append(msg)

        with patch(
            "tournament_scheduler.utils.rich_output.TournamentOutput.print_warning",
            side_effect=capture_warning,
        ):
            ParallelGamesConfig.from_dict({"JU12": 3})

        assert any("JU12" in m for m in called_messages), (
            f"Expected a warning mentioning JU12, got: {called_messages}"
        )
        assert any("2" in m for m in called_messages), (
            f"Expected a warning mentioning federation limit 2, got: {called_messages}"
        )

    def test_exceeding_limit_warning_contains_configured_value(self):
        """The warning message should mention the configured value."""
        called_messages = []

        def capture_warning(msg):
            called_messages.append(msg)

        with patch(
            "tournament_scheduler.utils.rich_output.TournamentOutput.print_warning",
            side_effect=capture_warning,
        ):
            ParallelGamesConfig.from_dict({"U12": 4})

        assert any("4" in m for m in called_messages), (
            f"Expected warning to mention configured value 4, got: {called_messages}"
        )

    def test_compliant_config_produces_no_warning(self):
        """A config within federation limits must not trigger any warning."""
        with patch(
            "tournament_scheduler.utils.rich_output.TournamentOutput.print_warning"
        ) as mock_warn:
            ParallelGamesConfig.from_dict({"JU12": 2, "U12": 2, "U7": 3})

        mock_warn.assert_not_called()

    def test_empty_config_produces_no_warning(self):
        """An empty config (all federation defaults) must not trigger any warning."""
        with patch(
            "tournament_scheduler.utils.rich_output.TournamentOutput.print_warning"
        ) as mock_warn:
            ParallelGamesConfig.from_dict({})

        mock_warn.assert_not_called()

    def test_multiple_violations_each_trigger_a_warning(self):
        """Multiple age groups above their limit each get their own warning call."""
        called_messages = []

        def capture_warning(msg):
            called_messages.append(msg)

        with patch(
            "tournament_scheduler.utils.rich_output.TournamentOutput.print_warning",
            side_effect=capture_warning,
        ):
            ParallelGamesConfig.from_dict({"JU12": 3, "U12": 5})

        assert any("JU12" in m for m in called_messages)
        assert any("U12" in m for m in called_messages)


class TestExistingBehaviour:
    """Regression: existing SeasonConfigError behaviour is unchanged."""

    def test_unknown_age_group_raises_season_config_error(self):
        with pytest.raises(SeasonConfigError, match="Ukjent aldersgruppe"):
            ParallelGamesConfig.from_dict({"UNKNOWN": 2})

    def test_non_positive_parallel_games_raises_season_config_error(self):
        with pytest.raises(SeasonConfigError, match="positivt heltall"):
            ParallelGamesConfig.from_dict({"U10": 0})

    def test_bool_value_raises_season_config_error(self):
        with pytest.raises(SeasonConfigError):
            ParallelGamesConfig.from_dict({"U10": True})
