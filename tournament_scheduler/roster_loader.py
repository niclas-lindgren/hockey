"""Loading roster config files for --generate-season.

Both JSON and YAML config files are supported, mirroring
`ParallelGamesConfig` in `season_config.py`. YAML support is optional and
only requires `pyyaml` to be installed — if it is not available, only JSON
files can be loaded and a clear Norwegian-language error is raised when a
`.yaml`/`.yml` file is requested.
"""

import json
import os

from tournament_scheduler.models import Roster, Team
from tournament_scheduler.season_config import KNOWN_AGE_GROUPS, _YAML_AVAILABLE, yaml


class RosterConfigError(ValueError):
    """Raised when a roster config file is malformed or invalid.

    Messages are in Norwegian to match the interactive CLI's user-facing
    language conventions (see tournament_scheduler_interactive.py).
    """


class RosterLoader:
    """Loads a roster config file (JSON or YAML) into a `Roster` of `Team` objects.

    Expected (canonical) format — a mapping of club name to a mapping of
    team label -> age group, supporting multiple teams per club::

        {
          "Jar": {"Jar 1": "U10", "Jar 2": "U11"},
          "Kongsberg": {"Kongsberg 1": "U10"}
        }

    This mirrors the structure used by `ParallelGamesConfig`. Malformed
    entries raise `RosterConfigError` with a Norwegian-language message.
    """

    @classmethod
    def from_dict(cls, data) -> Roster:
        """Build a `Roster` from an already-parsed dict, validating its contents."""
        if not isinstance(data, dict):
            raise RosterConfigError(
                "Ugyldig oppsett: forventet et oppslagsverk (dict) på toppnivå "
                f"som tilordner klubbnavn til lag, men fikk {type(data).__name__}."
            )

        if not data:
            raise RosterConfigError(
                "Ugyldig oppsett: spillerlisten (rosteret) er tom — ingen klubber funnet."
            )

        teams = []
        seen_labels = {}

        for club, team_map in data.items():
            if not isinstance(club, str) or not club.strip():
                raise RosterConfigError(
                    f"Ugyldig klubbnavn: {club!r}. Klubbnavn må være en ikke-tom tekststreng."
                )

            if not isinstance(team_map, dict):
                raise RosterConfigError(
                    f"Ugyldig oppsett for klubb '{club}': forventet et oppslagsverk som "
                    "tilordner lagnavn til aldersgruppe, f.eks. "
                    '{"Jar 1": "U10", "Jar 2": "U11"}, '
                    f"men fikk {type(team_map).__name__}."
                )

            if not team_map:
                raise RosterConfigError(
                    f"Klubben '{club}' har ingen lag oppført. Fjern klubben eller "
                    "legg til minst ett lag, f.eks. {\"" + club + " 1\": \"U10\"}."
                )

            for label, age_group in team_map.items():
                if not isinstance(label, str) or not label.strip():
                    raise RosterConfigError(
                        f"Ugyldig lagnavn for klubb '{club}': {label!r}. "
                        "Lagnavn må være en ikke-tom tekststreng."
                    )

                if not isinstance(age_group, str) or not age_group.strip():
                    raise RosterConfigError(
                        f"Ugyldig aldersgruppe for laget '{label}' (klubb '{club}'): "
                        f"{age_group!r}. Aldersgruppe må være en ikke-tom tekststreng."
                    )

                if age_group not in KNOWN_AGE_GROUPS:
                    raise RosterConfigError(
                        f"Ukjent aldersgruppe '{age_group}' for laget '{label}' (klubb '{club}'). "
                        f"Gyldige aldersgrupper er: {', '.join(sorted(KNOWN_AGE_GROUPS))}."
                    )

                if label in seen_labels:
                    other_club = seen_labels[label]
                    if other_club == club:
                        raise RosterConfigError(
                            f"Lagnavnet '{label}' er oppført flere ganger for klubben '{club}'. "
                            "Hvert lagnavn må være unikt."
                        )
                    raise RosterConfigError(
                        f"Lagnavnet '{label}' er oppført for både '{other_club}' og '{club}'. "
                        "Hvert lagnavn må være unikt på tvers av alle klubber."
                    )
                seen_labels[label] = club

                teams.append(Team(club=club, label=label, age_group=age_group))

        return Roster(teams=teams)

    @classmethod
    def from_file(cls, path: str) -> Roster:
        """Load and validate a roster config file (JSON or YAML, by file extension)."""
        if not os.path.isfile(path):
            raise RosterConfigError(f"Fant ikke spillerlistefilen (rosterfilen): {path}")

        _, ext = os.path.splitext(path)
        ext = ext.lower()

        with open(path, "r", encoding="utf-8") as handle:
            raw_text = handle.read()

        if ext in (".yaml", ".yml"):
            if not _YAML_AVAILABLE:
                raise RosterConfigError(
                    f"Kan ikke lese YAML-fil '{path}': pakken 'pyyaml' er ikke installert. "
                    "Installer 'pyyaml', eller bruk en JSON-konfigurasjonsfil i stedet."
                )
            try:
                data = yaml.safe_load(raw_text) or {}
            except Exception as exc:  # pragma: no cover - depends on optional dep
                raise RosterConfigError(f"Klarte ikke å tolke YAML-filen '{path}': {exc}")
        else:
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError as exc:
                raise RosterConfigError(f"Klarte ikke å tolke JSON-filen '{path}': {exc}")

        return cls.from_dict(data)
