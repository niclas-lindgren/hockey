"""Stage 1 — config parsing and Norwegian-language validation.

Loads ``input.xlsx`` (the canonical pipeline input workbook), validates it, and
writes the parsed, validated configuration to the Stage 1 checkpoint via
:class:`~tournament_scheduler.pipeline.state.PipelineState`.

Workbook input format (all fields required unless marked optional)::

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

The workbook ``Lag`` sheet is the standard team roster input. The internal config
shape still supports an external roster path for compatibility with lower-level helpers.

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
from .stage1_helpers import _load_json, _parse_config, validate_config
from .semantic_validation import build_semantic_prompt, parse_semantic_warnings
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
    """Load the effective (merged) config from ``input.xlsx`` + Stage 1 checkpoint.

    Reads the canonical ``input.xlsx`` workbook for human-editable fields
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
    ip = input_path or ckpt.get("input_path", "input.xlsx")
    raw = _load_json(ip)

    merged: dict[str, Any] = {}

    # From input.xlsx (canonical source)
    merged["start_date"] = raw.get("start_date")
    merged["end_date"] = raw.get("end_date")
    merged["parallel_games"] = raw.get("parallel_games", {})
    # Accept Norwegian alias deltakelser_per_lag; prefer it over the English key.
    target_ttc = raw.get("target_tournament_count")
    merged["target_tournament_count"] = raw.get("deltakelser_per_lag", target_ttc)
    merged["sources"] = raw.get("sources", [])

    # Age groups: explicit input workbook value only; downstream can fall back
    # to the plan when the input file truly omits the field.
    merged["age_groups"] = raw.get("age_groups", [])
    merged["age_groups_from_input"] = "age_groups" in raw

    # From Stage 1 checkpoint (computed)
    merged["teams"] = ckpt.get("teams", [])
    merged["round_length_minutes"] = ckpt.get("round_length_minutes", {})

    # Preserve other computed/metadata fields from the checkpoint
    if "input_path" in ckpt:
        merged["input_path"] = ckpt["input_path"]

    return merged


def run(
    input_path: str | os.PathLike[str],
    state: PipelineState,
    *,
    strict: bool = True,
    llm_client: Any = None,
) -> dict[str, Any]:
    """Parse and validate *input_path*, write the Stage 1 checkpoint.

    The checkpoint stores only **computed** fields (``teams`` expanded from a
    file reference, ``round_length_minutes`` with federation defaults applied).
    Human-editable fields (``start_date``, ``end_date``, ``age_groups``,
    ``parallel_games``, ``sources``) live exclusively in ``input.xlsx``.
    Use :func:`load_effective_config` to merge both sources transparently.

    Parameters
    ----------
    input_path:
        Path to ``input.xlsx`` (canonical pipeline input workbook).
    state:
        :class:`PipelineState` instance managing the work directory.
    strict:
        If ``True`` (default), raise :class:`Stage1Error` on any validation
        error and write the checkpoint with ``status=failed``.  If ``False``,
        continue with warnings logged but not raised.
    llm_client:
        Optional LLM client instance with a ``complete(system, user,
        temperature)`` method returning an object with a ``.text`` attribute.
        When provided, semantic feasibility checks are run after schema
        validation and any warnings are stored in the checkpoint under the
        ``semantic_warnings`` key.  When ``None`` (default) or when the
        client raises ``LMStudioUnavailableError``, semantic validation is
        silently skipped.

    Returns
    -------
    dict
        The computed config dict (teams, round_length_minutes, input_path,
        optionally semantic_warnings) that was written to the checkpoint.

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

    # Semantic (LLM) feasibility check — optional, skip gracefully if unavailable
    semantic_warnings: list[str] = []
    if llm_client is not None:
        try:
            # Build effective config for the prompt (merge raw fields with parsed config)
            effective = dict(config)
            effective.setdefault("start_date", raw.get("start_date", ""))
            effective.setdefault("end_date", raw.get("end_date", ""))
            effective.setdefault("age_groups", raw.get("age_groups", []))
            effective.setdefault("parallel_games", raw.get("parallel_games", {}))
            effective.setdefault("target_tournament_count",
                                 raw.get("deltakelser_per_lag",
                                         raw.get("target_tournament_count")))

            sys_p, usr_p = build_semantic_prompt(effective)
            response = llm_client.complete(sys_p, usr_p, temperature=0.1)
            semantic_warnings = parse_semantic_warnings(response.text)
        except Exception:  # noqa: BLE001
            # Includes LMStudioUnavailableError and any other transient errors
            pass

    if semantic_warnings:
        config["semantic_warnings"] = semantic_warnings

    state.write_stage(StageName.CONFIG, config, status=StageStatus.DONE)
    state.mark_done(StageName.CONFIG)
    return config


# CLI entry point — supports: python3 -m tournament_scheduler.pipeline.stage1_config
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Stage 1: config parsing and validation")
    parser.add_argument("--input", default="input.xlsx", help="Path to input.xlsx workbook")
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
