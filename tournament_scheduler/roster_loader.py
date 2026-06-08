"""Loading roster config files for --generate-season.

A roster config lists, for each club, the set of teams it enters into the
season plan grouped by age group.  Two formats are supported:

Flat format (legacy)::

    {
      "Jar": {"U10": ["Jar 1", "Jar 2"], "U11": ["Jar 1"]},
      "Kongsberg": {"U10": ["Kongsberg 1"], "U11": ["Kongsberg 1"]}
    }

Extended format (recommended) — includes federation defaults alongside clubs::

    {
      "federationDefaults": {
        "parallelGames": {"U10": 3, "U11": 2, ...},
        "maxTeamsPerTournament": {"U10": 6, "U11": 6, ...}
      },
      "clubs": {
        "Jar": {"U10": ["Jar 1", "Jar 2"], "U11": ["Jar 1"]},
        "Kongsberg": {"U10": ["Kongsberg 1"], "U11": ["Kongsberg 1"]}
      }
    }

Both JSON and YAML config files are supported. YAML support is optional and
only requires `pyyaml` to be installed — if it is not available, only JSON
files can be loaded and a clear Norwegian-language error is raised when a
`.yaml`/`.yml` file is requested.

Malformed entries (missing files, unparseable JSON/YAML, wrong top-level
shape, empty clubs, duplicate or blank team labels, unknown age groups,
etc.) raise `RosterConfigError` with a Norwegian-language message, so both
the scriptable CLI (`cli/season_command.py`) and the interactive flow
(`tournament_scheduler_interactive.py`) can catch and render errors
consistently via `TournamentOutput.print_error` / Norwegian console output.
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
    age group -> list of team labels, supporting multiple age groups and
    multiple teams per club::

        {
          "Jar": {"U10": ["Jar 1", "Jar 2"], "U11": ["Jar 1"]},
          "Kongsberg": {"U10": ["Kongsberg 1"], "U11": ["Kongsberg 1"]}
        }

    Malformed entries raise `RosterConfigError` with a Norwegian-language message.
    """

    @staticmethod
    def federation_defaults_from_dict(data: dict) -> dict:
        """Extract federation defaults from a parsed input file dict.

        Returns the ``federationDefaults`` sub-dict when the extended format is
        used, or an empty dict for the flat (legacy) format.
        """
        if not isinstance(data, dict):
            return {}
        return data.get("federationDefaults", {})

    @classmethod
    def from_dict(cls, data) -> Roster:
        """Build a `Roster` from an already-parsed dict, validating its contents.

        Accepts both the flat (legacy) format where top-level keys are club
        names, and the extended format where clubs are nested under a ``clubs``
        key alongside a ``federationDefaults`` section.
        """
        if not isinstance(data, dict):
            raise RosterConfigError(
                "Ugyldig oppsett: forventet et oppslagsverk (dict) på toppnivå "
                f"som tilordner klubbnavn til lag, men fikk {type(data).__name__}."
            )

        clubs_data = data["clubs"] if "clubs" in data else data

        if not isinstance(clubs_data, dict):
            raise RosterConfigError(
                "Ugyldig oppsett: 'clubs'-nøkkelen må inneholde et oppslagsverk av klubber."
            )

        if not clubs_data:
            raise RosterConfigError(
                "Ugyldig oppsett: spillerlisten (rosteret) er tom — ingen klubber funnet."
            )

        teams = []

        for club, age_group_map in clubs_data.items():
            if not isinstance(club, str) or not club.strip():
                raise RosterConfigError(
                    f"Ugyldig klubbnavn: {club!r}. Klubbnavn må være en ikke-tom tekststreng."
                )

            if not isinstance(age_group_map, dict):
                raise RosterConfigError(
                    f"Ugyldig oppsett for klubb '{club}': forventet et oppslagsverk som "
                    "tilordner aldersgruppe til liste med lagnavn, f.eks. "
                    '{"U10": ["Jar 1", "Jar 2"], "U11": ["Jar 1"]}, '
                    f"men fikk {type(age_group_map).__name__}."
                )

            if not age_group_map:
                raise RosterConfigError(
                    f"Klubben '{club}' har ingen lag oppført. Fjern klubben eller "
                    f'legg til minst ett lag, f.eks. {{"U10": ["{club} 1"]}}.'
                )

            seen_labels_for_club = set()

            for age_group, labels in age_group_map.items():
                if not isinstance(age_group, str) or not age_group.strip():
                    raise RosterConfigError(
                        f"Ugyldig aldersgruppe for klubb '{club}': {age_group!r}. "
                        "Aldersgruppe må være en ikke-tom tekststreng."
                    )

                if age_group not in KNOWN_AGE_GROUPS:
                    raise RosterConfigError(
                        f"Ukjent aldersgruppe '{age_group}' for klubb '{club}'. "
                        f"Gyldige aldersgrupper er: {', '.join(sorted(KNOWN_AGE_GROUPS))}."
                    )

                if not isinstance(labels, list) or not labels:
                    raise RosterConfigError(
                        f"Ugyldig lagoppføring for '{club}' / '{age_group}': forventet en "
                        f"ikke-tom liste med lagnavn, men fikk {type(labels).__name__}."
                    )

                for label in labels:
                    if not isinstance(label, str) or not label.strip():
                        raise RosterConfigError(
                            f"Ugyldig lagnavn for klubb '{club}' / '{age_group}': {label!r}. "
                            "Lagnavn må være en ikke-tom tekststreng."
                        )

                    key = (label, age_group)
                    if key in seen_labels_for_club:
                        raise RosterConfigError(
                            f"Lagnavnet '{label}' er oppført flere ganger for '{club}' / '{age_group}'. "
                            "Hvert lagnavn må være unikt innen samme aldersgruppe og klubb."
                        )
                    seen_labels_for_club.add(key)

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

    @classmethod
    def load_with_defaults(cls, path: str):
        """Load a roster config file and return ``(Roster, federation_defaults)``.

        ``federation_defaults`` is the dict under the ``federationDefaults`` key
        in the extended input format (contains ``parallelGames`` and
        ``maxTeamsPerTournament`` sub-dicts), or an empty dict for flat files.
        """
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

        roster = cls.from_dict(data)
        federation_defaults = cls.federation_defaults_from_dict(data)
        return roster, federation_defaults
