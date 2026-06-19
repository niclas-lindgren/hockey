"""Stage 1 validation and parsing helpers."""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .input_workbook import load_workbook_config

from ..models import Roster, Team
from ..roster_loader import RosterConfigError, RosterLoader
from ..season_config import (
    KNOWN_AGE_GROUPS,
    FEDERATION_PARALLEL_GAMES_DEFAULTS,
    FEDERATION_ROUND_LENGTH_DEFAULTS,
    ParallelGamesConfig,
    SeasonConfigError,
    AgeGroupSettings,
)

def validate_config(raw: dict[str, Any], input_path: Path) -> list[str]:
    """Validate *raw* config dict and return a list of Norwegian error messages.

    Returns an empty list if the config is valid.

    Parameters
    ----------
    raw:
        Parsed workbook config dict from ``input.xlsx``.
    input_path:
        Path to ``input.xlsx`` itself.  Used to resolve relative team-file
        paths relative to the workbook's directory rather than the process
        working directory.
    """
    errors: list[str] = []

    # --- Required fields ---
    if "start_date" not in raw:
        errors.append("Mangler felt 'start_date' (format: ÅÅÅÅ-MM-DD).")
    if "end_date" not in raw:
        errors.append("Mangler felt 'end_date' (format: ÅÅÅÅ-MM-DD).")

    # --- Date parsing ---
    start: date | None = None
    end: date | None = None
    if "start_date" in raw:
        start = _parse_date(raw["start_date"], "start_date", errors)
    if "end_date" in raw:
        end = _parse_date(raw["end_date"], "end_date", errors)

    if start and end:
        if end <= start:
            errors.append(
                f"'end_date' ({raw['end_date']}) må være etter 'start_date' ({raw['start_date']})."
            )
        diff = (end - start).days
        if diff < 7:
            errors.append(
                f"Perioden mellom start_date og end_date er bare {diff} dager — "
                "minst 7 dager er påkrevd for å planlegge turneringer."
            )

    # --- Age groups ---
    if "age_groups" in raw:
        raw_groups = raw["age_groups"]
        if not isinstance(raw_groups, list):
            errors.append("'age_groups' må være en liste (f.eks. [\"U10\", \"U12\"]).")
        else:
            for ag in raw_groups:
                if ag not in KNOWN_AGE_GROUPS:
                    valid = ", ".join(sorted(KNOWN_AGE_GROUPS))
                    errors.append(
                        f"Ukjent aldersgruppe '{ag}'. Gyldige verdier: {valid}."
                    )

    # --- Parallel games ---
    if "parallel_games" in raw:
        pg = raw["parallel_games"]
        if not isinstance(pg, dict):
            errors.append("'parallel_games' må være et objekt (f.eks. {\"U10\": 3}).")
        else:
            for ag, count in pg.items():
                if ag not in KNOWN_AGE_GROUPS:
                    valid = ", ".join(sorted(KNOWN_AGE_GROUPS))
                    errors.append(
                        f"Ukjent aldersgruppe '{ag}' i 'parallel_games'. Gyldige verdier: {valid}."
                    )
                elif not isinstance(count, int) or count < 1:
                    errors.append(
                        f"'parallel_games[\"{ag}\"]' må være et positivt heltall, fikk: {count!r}."
                    )
                else:
                    fed_max = FEDERATION_PARALLEL_GAMES_DEFAULTS.get(ag)
                    if fed_max is not None and count > fed_max:
                        errors.append(
                            f"'parallel_games[\"{ag}\"]' = {count} overskrider "
                            f"forbundets maksimum ({fed_max}) for {ag}."
                        )

    # --- Round length (minutes) ---
    if "round_length_minutes" in raw:
        rl = raw["round_length_minutes"]
        if not isinstance(rl, dict):
            errors.append(
                "'round_length_minutes' må være et objekt (f.eks. {\"U10\": 10})."
            )
        else:
            for ag, minutes in rl.items():
                if ag not in KNOWN_AGE_GROUPS:
                    valid = ", ".join(sorted(KNOWN_AGE_GROUPS))
                    errors.append(
                        f"Ukjent aldersgruppe '{ag}' i 'round_length_minutes'. Gyldige verdier: {valid}."
                    )
                elif not isinstance(minutes, int) or minutes < 1:
                    errors.append(
                        f"'round_length_minutes[\"{ag}\"]' må være et positivt heltall, fikk: {minutes!r}."
                    )

    # --- Target tournament count / deltakelser per lag ---
    # Accept both the old English key and the new Norwegian alias.
    # If both are present, deltakelser_per_lag wins.
    target_raw = raw.get("deltakelser_per_lag", raw.get("target_tournament_count"))
    if target_raw is not None:
        if not isinstance(target_raw, int) or target_raw < 1:
            errors.append(
                f"'deltakelser_per_lag' (eller 'target_tournament_count') må være et "
                f"positivt heltall (f.eks. 6), fikk: {target_raw!r}."
            )

    # --- Teams / roster ---
    if "teams" not in raw:
        errors.append(
            "Mangler felt 'teams'. Oppgi en liste med lag eller en sti til en lagfil."
        )
    else:
        teams_val = raw["teams"]
        if isinstance(teams_val, str):
            # External file reference — resolve relative to the workbook directory
            # so the check is not sensitive to the process working directory.
            teams_path = (input_path.parent / teams_val).resolve()
            if not teams_path.exists():
                errors.append(
                    f"Lagfilen '{teams_val}' finnes ikke. "
                    "Sjekk at stien er riktig."
                )
        elif isinstance(teams_val, list):
            if not teams_val:
                errors.append("'teams' er en tom liste — legg til minst ett lag.")
            else:
                errors.extend(_validate_team_list(teams_val))
        else:
            errors.append(
                "'teams' må være enten en liste med lag-objekter eller en sti til en lagfil (streng)."
            )

    return errors


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_json(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Load the standard Excel workbook input as the canonical raw config dict.

    The function name is kept for compatibility with existing imports.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Finner ikke konfigurasjonsfilen '{p}'. Sjekk at stien er riktig."
        )
    if p.suffix.lower() not in {".xlsx", ".xlsm"}:
        raise ValueError(
            f"Konfigurasjonsfilen '{p}' må være en Excel-arbeidsbok (.xlsx). "
            "JSON input er ikke lenger støttet som pipeline-standard."
        )
    return load_workbook_config(p)


def _parse_date(value: Any, field: str, errors: list[str]) -> date | None:
    if not isinstance(value, str):
        errors.append(f"'{field}' må være en tekststreng (format: ÅÅÅÅ-MM-DD), fikk: {value!r}.")
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        errors.append(
            f"'{field}' har ugyldig datoformat '{value}'. Bruk ÅÅÅÅ-MM-DD (f.eks. 2025-09-01)."
        )
        return None


def _validate_team_list(teams: list[Any]) -> list[str]:
    errors: list[str] = []
    required_keys = {"club", "label", "age_group"}
    valid_teams: list[tuple[int, dict[str, Any]]] = []  # (1-based index, team dict)
    for i, team in enumerate(teams):
        prefix = f"Lag #{i + 1}"
        if not isinstance(team, dict):
            errors.append(f"{prefix}: forventet et objekt, fikk {type(team).__name__!r}.")
            continue
        valid_teams.append((i + 1, team))
        missing = required_keys - team.keys()
        if missing:
            errors.append(
                f"{prefix} ('{team.get('label', '?')}'): mangler felt: "
                + ", ".join(f"'{k}'" for k in sorted(missing))
                + "."
            )
        ag = team.get("age_group")
        if ag and ag not in KNOWN_AGE_GROUPS:
            valid = ", ".join(sorted(KNOWN_AGE_GROUPS))
            errors.append(
                f"{prefix} ('{team.get('label', '?')}'): ukjent aldersgruppe '{ag}'. "
                f"Gyldige verdier: {valid}."
            )
    # Detect duplicate labels
    label_to_indices: dict[str, list[int]] = {}
    for idx, team in valid_teams:
        label = team.get("label")
        if label is not None:
            label_to_indices.setdefault(label, []).append(idx)
    for label, indices in label_to_indices.items():
        if len(indices) > 1:
            lag_liste = " og ".join(f"Lag #{n}" for n in indices)
            errors.append(
                f"duplikat 'label': {lag_liste} har samme etikett '{label}'."
            )
    return errors


def _parse_config(raw: dict[str, Any], input_path: str | os.PathLike[str]) -> dict[str, Any]:
    """Build the Stage 1 checkpoint dict with only **computed** fields.

    Human-editable fields (start_date, end_date, age_groups, parallel_games,
    target_tournament_count / deltakelser_per_lag, sources) are intentionally excluded — they live only in ``input.xlsx``.
    """

    # Round length (minutes) — explicit values override federation defaults
    rl_dict: dict[str, int] = dict(FEDERATION_ROUND_LENGTH_DEFAULTS)
    if "round_length_minutes" in raw:
        rl_raw = raw["round_length_minutes"]
        if isinstance(rl_raw, dict):
            rl_dict.update({k: int(v) for k, v in rl_raw.items()})

    # Teams — expand from file reference if needed
    teams_val = raw["teams"]
    if isinstance(teams_val, str):
        roster, _ = RosterLoader.load_with_defaults(teams_val)
        teams_data = [
            {"club": t.club, "label": t.label, "age_group": t.age_group}
            for t in roster.teams
        ]
    else:
        teams_data = list(teams_val)

    result: dict[str, Any] = {
        "input_path": str(Path(input_path).resolve()),
        "teams": teams_data,
        "round_length_minutes": rl_dict,
    }

    if "fairness_thresholds" in raw:
        result["fairness_thresholds"] = dict(raw["fairness_thresholds"])
    # Accept both the old English key and the new Norwegian alias.
    # If both are present, deltakelser_per_lag wins.
    target_raw = raw.get("deltakelser_per_lag", raw.get("target_tournament_count"))
    if target_raw is not None:
        result["target_tournament_count"] = int(target_raw)

    return result


# ---------------------------------------------------------------------------
