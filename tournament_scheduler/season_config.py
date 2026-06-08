"""Season-scheduling configuration loaders.

Currently provides `ParallelGamesConfig`, which loads a small per-age-group
config of the form::

    {
        "U7": {"parallelGames": 4},
        "U10": {"parallelGames": 3}
    }

The same structure is intended to be mirrored by the roster config (club/team
roster) added alongside the season-scheduling extension.

Both JSON and YAML config files are supported. YAML support is optional and
only requires `pyyaml` to be installed — if it is not available, only JSON
files can be loaded and a clear Norwegian-language error is raised when a
`.yaml`/`.yml` file is requested.
"""

import json
import os
from dataclasses import dataclass
from typing import Dict, Optional, Union

try:
    import yaml  # type: ignore

    _YAML_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when pyyaml is missing
    yaml = None
    _YAML_AVAILABLE = False


# Sensible defaults applied when an age group is not present in the config file.
DEFAULT_PARALLEL_GAMES = 2

# Known age groups (boys + girls/"jenter") — used to validate config keys.
KNOWN_AGE_GROUPS = {
    "U7", "U8", "U9", "U10", "U11", "U12",
    "JU10", "JU11", "JU12", "JU13",
}


class SeasonConfigError(ValueError):
    """Raised when a season-scheduling config file is malformed or invalid.

    Messages are in Norwegian to match the interactive CLI's user-facing
    language conventions (see tournament_scheduler_interactive.py).
    """


@dataclass(frozen=True)
class AgeGroupSettings:
    """Per-age-group settings for the season planner.

    Currently only `parallel_games` is defined; more age-group-specific
    settings may be added to this config later (see PROJECT.md).
    """

    parallel_games: int = DEFAULT_PARALLEL_GAMES


class ParallelGamesConfig:
    """Loads and validates the per-age-group parallel-games configuration.

    Example config (JSON)::

        {
          "U7": {"parallelGames": 4},
          "U10": {"parallelGames": 3}
        }

    Unknown age groups and non-positive `parallelGames` values raise
    `SeasonConfigError` with a Norwegian-language message. Age groups absent
    from the config fall back to `DEFAULT_PARALLEL_GAMES`.
    """

    def __init__(self, settings: Optional[Dict[str, AgeGroupSettings]] = None):
        self._settings: Dict[str, AgeGroupSettings] = settings or {}

    @classmethod
    def from_dict(cls, data: Dict[str, Union[Dict, int]]) -> "ParallelGamesConfig":
        """Build a config from an already-parsed dict, validating its contents.

        Each value may either be a mapping like `{"parallelGames": 3}` or a
        bare integer (shorthand for the same thing).
        """
        if not isinstance(data, dict):
            raise SeasonConfigError(
                "Ugyldig konfigurasjon: forventet et oppslagsverk (dict) på toppnivå, "
                f"men fikk {type(data).__name__}."
            )

        settings: Dict[str, AgeGroupSettings] = {}
        for age_group, raw_value in data.items():
            if age_group not in KNOWN_AGE_GROUPS:
                raise SeasonConfigError(
                    f"Ukjent aldersgruppe '{age_group}' i konfigurasjonen. "
                    f"Gyldige aldersgrupper er: {', '.join(sorted(KNOWN_AGE_GROUPS))}."
                )

            parallel_games = cls._extract_parallel_games(age_group, raw_value)

            if parallel_games <= 0:
                raise SeasonConfigError(
                    f"Ugyldig verdi for 'parallelGames' for aldersgruppe '{age_group}': "
                    f"{parallel_games}. Verdien må være et positivt heltall."
                )

            settings[age_group] = AgeGroupSettings(parallel_games=parallel_games)

        return cls(settings)

    @staticmethod
    def _extract_parallel_games(age_group: str, raw_value: Union[Dict, int]) -> int:
        if isinstance(raw_value, bool):
            # bool is a subclass of int — explicitly reject it as a config value.
            raise SeasonConfigError(
                f"Ugyldig verdi for aldersgruppe '{age_group}': forventet et heltall "
                f"for 'parallelGames', men fikk en boolsk verdi ({raw_value})."
            )

        if isinstance(raw_value, int):
            return raw_value

        if isinstance(raw_value, dict):
            if "parallelGames" not in raw_value:
                raise SeasonConfigError(
                    f"Mangler 'parallelGames' for aldersgruppe '{age_group}'. "
                    "Forventet format: {\"<aldersgruppe>\": {\"parallelGames\": <tall>}}."
                )
            value = raw_value["parallelGames"]
            if isinstance(value, bool) or not isinstance(value, int):
                raise SeasonConfigError(
                    f"Ugyldig verdi for 'parallelGames' for aldersgruppe '{age_group}': "
                    f"{value!r}. Verdien må være et heltall."
                )
            return value

        raise SeasonConfigError(
            f"Ugyldig verdi for aldersgruppe '{age_group}': {raw_value!r}. "
            "Forventet enten et heltall eller et oppslagsverk med 'parallelGames'."
        )

    @classmethod
    def from_file(cls, path: str) -> "ParallelGamesConfig":
        """Load and validate a config file (JSON or YAML, by file extension)."""
        if not os.path.isfile(path):
            raise SeasonConfigError(f"Fant ikke konfigurasjonsfilen: {path}")

        _, ext = os.path.splitext(path)
        ext = ext.lower()

        with open(path, "r", encoding="utf-8") as handle:
            raw_text = handle.read()

        if ext in (".yaml", ".yml"):
            if not _YAML_AVAILABLE:
                raise SeasonConfigError(
                    f"Kan ikke lese YAML-fil '{path}': pakken 'pyyaml' er ikke installert. "
                    "Installer 'pyyaml', eller bruk en JSON-konfigurasjonsfil i stedet."
                )
            try:
                data = yaml.safe_load(raw_text) or {}
            except Exception as exc:  # pragma: no cover - depends on optional dep
                raise SeasonConfigError(f"Klarte ikke å tolke YAML-filen '{path}': {exc}")
        else:
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError as exc:
                raise SeasonConfigError(f"Klarte ikke å tolke JSON-filen '{path}': {exc}")

        return cls.from_dict(data)

    def parallel_games_for(self, age_group: str) -> int:
        """Return the configured parallel-games count for an age group.

        Falls back to `DEFAULT_PARALLEL_GAMES` when the age group is not
        present in the loaded configuration.
        """
        settings = self._settings.get(age_group)
        if settings is None:
            return DEFAULT_PARALLEL_GAMES
        return settings.parallel_games

    def settings_for(self, age_group: str) -> AgeGroupSettings:
        """Return the full `AgeGroupSettings` for an age group (with defaults)."""
        return self._settings.get(age_group, AgeGroupSettings())

    def configured_age_groups(self) -> Dict[str, AgeGroupSettings]:
        """Return a copy of the explicitly-configured age-group settings."""
        return dict(self._settings)
