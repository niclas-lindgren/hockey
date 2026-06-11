"""Stage 1 — config parsing and Norwegian-language validation.

Loads ``input.json`` (the canonical pipeline input format), validates it, and
writes the parsed, validated configuration to the Stage 1 checkpoint via
:class:`~tournament_scheduler.pipeline.state.PipelineState`.

Input JSON format (all fields required unless marked optional)::

    {
        "start_date": "YYYY-MM-DD",
        "end_date": "YYYY-MM-DD",
        "age_groups": ["U10", "U12", ...],          // optional — defaults to all
        "parallel_games": {"U10": 3, "U7": 4, ...}, // optional
        "round_length_minutes": {"U10": 10, ...},   // optional — defaults to federation values
        "teams": [                                   // list of teams (roster)
            {"club": "Kongsberg", "label": "Kongsberg U10A", "age_group": "U10"},
            ...
        ]
    }

The ``teams`` section can also be an external file path (string) that points to
a roster JSON/YAML file loadable by :class:`~tournament_scheduler.roster_loader.RosterLoader`.

Norwegian error messages are emitted via :func:`validate_config` as a list of
human-readable strings so callers can surface them directly to users.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

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
from .state import PipelineState, StageName, StageStatus

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class Stage1Error(ValueError):
    """Raised when Stage 1 cannot proceed due to validation errors."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("\n".join(errors))


def load_effective_config(
    state: PipelineState,
    *,
    input_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Load the effective (merged) config from ``input.json`` + Stage 1 checkpoint.

    Reads the canonical ``input.json`` for human-editable fields
    (``start_date``, ``end_date``, ``age_groups``, ``parallel_games``,
    ``sources``) and merges in the computed fields (``teams``,
    ``round_length_minutes``) from the Stage 1 checkpoint.

    Returns a dict with the same shape that downstream stages expect,
    so callers see no API change.
    """
    ckpt = state.read_stage(StageName.CONFIG)
    if not ckpt:
        return {}

    # Resolve input path: checkpoint > parameter > default
    ip = input_path or ckpt.get("input_path", "input.json")
    raw = _load_json(ip)

    merged: dict[str, Any] = {}

    # From input.json (canonical source)
    merged["start_date"] = raw.get("start_date")
    merged["end_date"] = raw.get("end_date")
    merged["parallel_games"] = raw.get("parallel_games", {})
    merged["sources"] = raw.get("sources", [])

    # Age groups: prefer input.json, fall back to derived from Stage 1
    if "age_groups" in raw:
        merged["age_groups"] = raw["age_groups"]
    elif "derived_age_groups" in ckpt:
        merged["age_groups"] = ckpt["derived_age_groups"]
    else:
        merged["age_groups"] = []

    # From Stage 1 checkpoint (computed)
    merged["teams"] = ckpt.get("teams", [])
    merged["round_length_minutes"] = ckpt.get("round_length_minutes", {})

    # Preserve other computed/metadata fields from the checkpoint
    for key in ("input_path", "derived_age_groups"):
        if key in ckpt:
            merged[key] = ckpt[key]

    return merged


def run(
    input_path: str | os.PathLike[str],
    state: PipelineState,
    *,
    strict: bool = True,
) -> dict[str, Any]:
    """Parse and validate *input_path*, write the Stage 1 checkpoint.

    The checkpoint stores only **computed** fields (``teams`` expanded from a
    file reference, ``round_length_minutes`` with federation defaults applied).
    Human-editable fields (``start_date``, ``end_date``, ``age_groups``,
    ``parallel_games``, ``sources``) live exclusively in ``input.json``.
    Use :func:`load_effective_config` to merge both sources transparently.

    Parameters
    ----------
    input_path:
        Path to ``input.json`` (canonical pipeline input).
    state:
        :class:`PipelineState` instance managing the work directory.
    strict:
        If ``True`` (default), raise :class:`Stage1Error` on any validation
        error and write the checkpoint with ``status=failed``.  If ``False``,
        continue with warnings logged but not raised.

    Returns
    -------
    dict
        The computed config dict (teams, round_length_minutes, input_path)
        that was written to the checkpoint.

    Raises
    ------
    Stage1Error
        When *strict* is ``True`` and validation produces errors.
    FileNotFoundError
        When *input_path* does not exist.
    """
    raw = _load_json(input_path)
    errors = validate_config(raw)

    if errors:
        if strict:
            raise Stage1Error(errors)
        # Non-strict: record errors but continue with best-effort parsing
        state.write_stage(
            StageName.CONFIG,
            {"errors": errors, "raw": raw},
            status=StageStatus.FAILED,
        )
        return {"errors": errors}

    # Parse validated config into structured objects
    state.write_stage(StageName.CONFIG, {}, status=StageStatus.RUNNING)
    config = _parse_config(raw, input_path)

    state.write_stage(StageName.CONFIG, config, status=StageStatus.DONE)
    state.mark_done(StageName.CONFIG)
    return config


def validate_config(raw: dict[str, Any]) -> list[str]:
    """Validate *raw* config dict and return a list of Norwegian error messages.

    Returns an empty list if the config is valid.

    Parameters
    ----------
    raw:
        Parsed JSON dict from ``input.json``.
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

    # --- Teams / roster ---
    if "teams" not in raw:
        errors.append(
            "Mangler felt 'teams'. Oppgi en liste med lag eller en sti til en lagfil."
        )
    else:
        teams_val = raw["teams"]
        if isinstance(teams_val, str):
            # External file reference — check it exists
            if not Path(teams_val).exists():
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
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Finner ikke konfigurasjonsfilen '{p}'. Sjekk at stien er riktig."
        )
    with p.open(encoding="utf-8") as fh:
        return json.load(fh)


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
    for i, team in enumerate(teams):
        prefix = f"Lag #{i + 1}"
        if not isinstance(team, dict):
            errors.append(f"{prefix}: forventet et objekt, fikk {type(team).__name__!r}.")
            continue
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
    return errors


def _parse_config(raw: dict[str, Any], input_path: str | os.PathLike[str]) -> dict[str, Any]:
    """Build the Stage 1 checkpoint dict with only **computed** fields.

    Human-editable fields (start_date, end_date, age_groups, parallel_games,
    sources) are intentionally excluded — they live only in ``input.json``.
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

    # Derived age groups: only stored when input.json has no explicit list
    if "age_groups" not in raw:
        result["derived_age_groups"] = sorted(
            {t["age_group"] for t in teams_data}
        )

    return result


# ---------------------------------------------------------------------------
# CLI entry point — supports: python3 -m tournament_scheduler.pipeline.stage1_config
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Stage 1: config parsing and validation")
    parser.add_argument("--input", default="input.json", help="Path to input.json")
    parser.add_argument("--work-dir", default=".pipeline", help="Pipeline work directory")
    cli_args = parser.parse_args()

    from .state import PipelineState  # noqa: E402

    _state = PipelineState(cli_args.work_dir)
    try:
        _result = run(cli_args.input, _state)
        _raw = _load_json(cli_args.input)
        print(f"Stage 1 OK — {len(_result.get('teams', []))} lag, "
              f"{_raw.get('start_date')} til {_raw.get('end_date')}")
        sys.exit(0)
    except (Stage1Error, FileNotFoundError) as _e:
        print(str(_e), file=sys.stderr)
        sys.exit(1)
