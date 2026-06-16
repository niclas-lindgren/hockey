"""Loading roster config files for --generate-season.

A roster config lists, for each club, the set of teams it enters into the
season plan grouped by age group.  Two base formats are supported:

Flat format (legacy)::

    {
      "Jar": {"U10": ["Jar 1", "Jar 2"], "U11": ["Jar 1"]},
      "Kongsberg": {"U10": ["Kongsberg 1"], "U11": ["Kongsberg 1"]}
    }

Extended format (recommended) — includes federation defaults alongside clubs::

    {
      "federationDefaults": {
        "parallelGames": {"U10": 3, "U11": 2, ...}
      },
      "clubs": {
        "Jar": {"U10": ["Jar 1", "Jar 2"], "U11": ["Jar 1"]},
        "Kongsberg": {"U10": ["Kongsberg 1"], "U11": ["Kongsberg 1"]}
      }
    }

Optionally, the extended format also supports a ``neighborClubs`` section
for listing clubs from neighboring regions (e.g. Oslo-area clubs for girls'
cross-region tournaments). These teams keep their ``region`` metadata so
reports/export round-trips can distinguish them from RVV teams::

    {
      "federationDefaults": { ... },
      "clubs": {
        "Jar": {"U10": ["Jar 1", "Jar 2"]}
      },
      "neighborClubs": {
        "Oslo": {"JU10": ["Oslo 1"]},
        "Furuset": {"JU10": ["Furuset JU10"]}
      }
    }

Teams from ``neighborClubs`` get their ``region`` set to the club name
(e.g. ``"Oslo"``) so downstream tools can distinguish RVV teams from
cross-region teams. ``skill_level`` is parsed here as well and passed
through unchanged so the planner can use it later when forming tournaments.

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

from typing import Optional

from tournament_scheduler.models import Roster, Team
from tournament_scheduler.season_config import KNOWN_AGE_GROUPS, _YAML_AVAILABLE, yaml


class RosterConfigError(ValueError):
    """Raised when a roster config file is malformed or invalid.

    Messages are in Norwegian to match the interactive CLI's user-facing
    language conventions (see tournament_scheduler_interactive.py).
    """


class RosterLoader:
    """Loads a roster config file (JSON or YAML) into a `Roster` of `Team` objects.

    Expected formats — see module docstring for flat, extended, and
    neighbor-club variants.
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
    def _parse_clubs_section(
        cls,
        clubs_data: dict,
        *,
        region: str = "RVV",
        section_label: str = "clubs",
    ) -> list[Team]:
        """Parse a club-name -> age-group -> team-labels mapping into Team objects.

        Parameters
        ----------
        clubs_data:
            Dict mapping club name to dict of age group -> list of team labels.
        region:
            Region metadata value to assign to every team parsed (default
            ``"RVV"``). The scheduler keeps this for reporting and
            round-tripping, not as a hard constraint.
        section_label:
            Norwegian label for the config section (used in error messages).

        Returns
        -------
        list[Team]
            Parsed team objects in iteration order.

        Raises
        ------
        RosterConfigError
            On any validation error with a Norwegian-language message.
        """
        if not isinstance(clubs_data, dict):
            raise RosterConfigError(
                f"Ugyldig oppsett: '{section_label}'-nøkkelen må inneholde "
                "et oppslagsverk av klubber."
            )

        teams: list[Team] = []

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

                for entry in labels:
                    label: str
                    skill_level: Optional[int] = None
                    if isinstance(entry, str):
                        label = entry
                    elif isinstance(entry, dict):
                        if "label" not in entry or not isinstance(entry["label"], str) or not entry["label"].strip():
                            raise RosterConfigError(
                                f"Ugyldig lagoppføring for klubb '{club}' / '{age_group}': "
                                f"{entry!r}. Når et lagnavn skrives som et objekt, må det ha "
                                'en "label"-nøkkel med en ikke-tom tekststreng, '
                                'f.eks. {"label": "Jar 1", "skillLevel": 5}.'
                            )
                        label = entry["label"]
                        sl = entry.get("skillLevel")
                        if sl is not None:
                            if not isinstance(sl, int) or sl < 1 or sl > 10:
                                raise RosterConfigError(
                                    f"Ugyldig skillLevel for '{label}' / '{club}' / '{age_group}': "
                                    f"{sl!r}. SkillLevel må være et heltall mellom 1 og 10."
                                )
                            skill_level = sl
                    else:
                        raise RosterConfigError(
                            f"Ugyldig lagoppføring for klubb '{club}' / '{age_group}': "
                            f"{entry!r}. Forventet en tekststreng (lagnavn) eller et "
                            'objekt med "label"-nøkkel, '
                            f"men fikk {type(entry).__name__}."
                        )

                    if not label.strip():
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

                    teams.append(Team(club=club, label=label, age_group=age_group, region=region, skill_level=skill_level))

        return teams

    @classmethod
    def from_dict(cls, data) -> Roster:
        """Build a `Roster` from an already-parsed dict, validating its contents.

        Accepts the flat (legacy) format, the extended format with a ``clubs``
        key, and the extended format with an optional ``neighborClubs`` section.
        """
        if not isinstance(data, dict):
            raise RosterConfigError(
                "Ugyldig oppsett: forventet et oppslagsverk (dict) på toppnivå "
                f"som tilordner klubbnavn til lag, men fikk {type(data).__name__}."
            )

        is_extended = "clubs" in data
        clubs_data = data["clubs"] if is_extended else data

        if not clubs_data:
            raise RosterConfigError(
                "Ugyldig oppsett: spillerlisten (rosteret) er tom — ingen klubber funnet."
            )

        teams = cls._parse_clubs_section(clubs_data, region="RVV", section_label="clubs")

        # Parse optional neighborClubs in extended format only
        if is_extended and "neighborClubs" in data:
            neighbor_clubs_data = data["neighborClubs"]
            if not isinstance(neighbor_clubs_data, dict):
                raise RosterConfigError(
                    "Ugyldig oppsett: 'neighborClubs'-nøkkelen må inneholde "
                    "et oppslagsverk av klubber."
                )
            if neighbor_clubs_data:
                neighbor_teams = cls._parse_clubs_section(
                    neighbor_clubs_data,
                    section_label="neighborClubs",
                )
                # Re-set region for each neighbor-club team to its club name
                for t in neighbor_teams:
                    object.__setattr__(t, "region", t.club)
                teams.extend(neighbor_teams)

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
        in the extended input format (contains ``parallelGames``), or an empty
        dict for flat files.
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
