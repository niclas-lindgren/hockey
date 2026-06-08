"""Loading roster config files for --generate-season."""

import json
import os
import sys

from tournament_scheduler.models import Roster, Team


class RosterLoader:
    """Loads a roster config file (JSON) into a `Roster` of `Team` objects.

    Expected format::

        {
          "Jar": {"Jar 1": "U10", "Jar 2": "U11"},
          "Kongsberg": {"Kongsberg 1": "U10"}
        }

    or, equivalently, a flat list of entries::

        [
          {"club": "Jar", "label": "Jar 1", "age_group": "U10"},
          ...
        ]
    """

    @staticmethod
    def load(path: str) -> Roster:
        if not os.path.isfile(path):
            print(f"Error: Roster file not found: {path}", file=sys.stderr)
            sys.exit(1)

        with open(path, 'r', encoding='utf-8') as handle:
            try:
                data = json.load(handle)
            except json.JSONDecodeError as exc:
                print(f"Error: Could not parse roster file '{path}': {exc}", file=sys.stderr)
                sys.exit(1)

        teams = []
        if isinstance(data, dict):
            for club, team_map in data.items():
                if not isinstance(team_map, dict):
                    print(f"Error: Expected a mapping of team label -> age group for club '{club}'", file=sys.stderr)
                    sys.exit(1)
                for label, age_group in team_map.items():
                    teams.append(Team(club=club, label=label, age_group=age_group))
        elif isinstance(data, list):
            for entry in data:
                try:
                    teams.append(Team(club=entry['club'], label=entry['label'], age_group=entry['age_group']))
                except (KeyError, TypeError):
                    print(f"Error: Roster entries must have 'club', 'label', and 'age_group': {entry}", file=sys.stderr)
                    sys.exit(1)
        else:
            print(f"Error: Unsupported roster file format in '{path}' — expected an object or a list", file=sys.stderr)
            sys.exit(1)

        if not teams:
            print(f"Error: No teams found in roster file '{path}'", file=sys.stderr)
            sys.exit(1)

        return Roster(teams=teams)
