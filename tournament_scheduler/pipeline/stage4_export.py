"""Stage 4 — multi-format export (Excel, iCal, CSV).

Reads the Stage 3 plan checkpoint, reconstructs a :class:`SeasonPlan` from it,
and writes three output files:

- ``<export_dir>/season_plan.xlsx``   — Excel workbook via :class:`SeasonPlanExporter`
- ``<export_dir>/season_plan.ics``    — iCal feed via :class:`ICalExporter`
- ``<export_dir>/season_plan.csv``    — flat game CSV + ``_overview.csv`` via :class:`CsvExporter`
- ``<export_dir>/season_plan.html``   — interactive HTML overview via :class:`~tournament_scheduler.html.html_exporter.HtmlExporter`

File paths are written to the Stage 4 checkpoint.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ..models import Game, Roster, SeasonPlan, Team, Tournament
from ..excel.plan_exporter import SeasonPlanExporter
from ..ical.ical_exporter import ICalExporter
from ..csv.csv_exporter import CsvExporter
from ..html.html_exporter import HtmlExporter
from ..spond.spond_exporter import SpondExporter
from .state import PipelineState, StageName, StageStatus

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_EXPORT_DIR = "export"
DEFAULT_BASENAME = "season_plan"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class Stage4Error(RuntimeError):
    """Raised when Stage 4 export fails."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run(
    plan_checkpoint: dict[str, Any],
    state: PipelineState,
    *,
    export_dir: str | os.PathLike[str] = DEFAULT_EXPORT_DIR,
    basename: str = DEFAULT_BASENAME,
    strict: bool = True,
) -> dict[str, Any]:
    """Export the Stage 3 plan to Excel, iCal, and CSV.

    Parameters
    ----------
    plan_checkpoint:
        Stage 3 checkpoint data (must contain a ``plan`` key).
    state:
        :class:`PipelineState` managing the work directory.
    export_dir:
        Directory where output files are written (created if needed).
    basename:
        Base filename without extension (default ``season_plan``).
    strict:
        If ``True``, raise :class:`Stage4Error` on any export failure.

    Returns
    -------
    dict
        Checkpoint data with output file paths.
    """
    state.write_stage(StageName.EXPORT, {}, status=StageStatus.RUNNING)

    plan_dict = plan_checkpoint.get("plan", {})
    if not plan_dict:
        reason = "Ingen plan funnet i Stage 3 checkpoint — kjør Stage 3 først."
        state.mark_failed(StageName.EXPORT, error=reason)
        if strict:
            raise Stage4Error(reason)
        return {}

    plan = _dict_to_plan(plan_dict)
    export_path = Path(export_dir)
    export_path.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    output_files: dict[str, str] = {}

    # --- Excel ---
    try:
        excel_path = str(export_path / f"{basename}.xlsx")
        rules_report = plan_checkpoint.get("rules_report")
        SeasonPlanExporter().export(plan, excel_path, rules_report=rules_report)
        output_files["excel"] = excel_path
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Excel-eksport feilet: {exc}")

    # --- iCal ---
    try:
        ical_path = str(export_path / f"{basename}.ics")
        ICalExporter().export(plan, ical_path)
        output_files["ical"] = ical_path
    except Exception as exc:  # noqa: BLE001
        errors.append(f"iCal-eksport feilet: {exc}")

    # --- CSV ---
    try:
        csv_path = str(export_path / f"{basename}.csv")
        games_path, overview_path = CsvExporter().export(plan, csv_path)
        output_files["csv_games"] = games_path
        output_files["csv_overview"] = overview_path
    except Exception as exc:  # noqa: BLE001
        errors.append(f"CSV-eksport feilet: {exc}")

    # --- HTML ---
    try:
        html_path = str(export_path / f"{basename}.html")
        # Pass scrape metadata from cache for navbar
        meta = None
        try:
            from .cache_manager import ScrapedDataCache
            meta = ScrapedDataCache(state.work_dir).read().get("_meta")
        except Exception:
            pass
        HtmlExporter().export(plan, html_path, meta=meta, output_files=output_files)
        output_files["html"] = html_path
    except Exception as exc:  # noqa: BLE001
        errors.append(f"HTML-eksport feilet: {exc}")

    # --- Spond ---
    try:
        spond_path = str(export_path / f"{basename}_spond.xlsx")
        SpondExporter().export(plan, spond_path)
        output_files["spond"] = spond_path
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Spond-eksport feilet: {exc}")

    checkpoint: dict[str, Any] = {
        "output_files": output_files,
        "errors": errors,
    }

    if errors and strict:
        state.write_stage(StageName.EXPORT, checkpoint, status=StageStatus.FAILED)
        state.mark_failed(StageName.EXPORT, error="; ".join(errors))
        raise Stage4Error("\n".join(errors))

    status = StageStatus.DONE if not errors else StageStatus.FAILED
    state.write_stage(StageName.EXPORT, checkpoint, status=status)
    if not errors:
        state.mark_done(StageName.EXPORT)
    return checkpoint


# ---------------------------------------------------------------------------
# Deserialisation
# ---------------------------------------------------------------------------


def _dict_to_plan(d: dict[str, Any]) -> SeasonPlan:
    """Reconstruct a :class:`SeasonPlan` from the checkpoint dict."""
    tournaments: list[Tournament] = []

    for t_dict in d.get("tournaments", []):
        teams = [
            Team(
                club=tm["club"],
                label=tm["label"],
                age_group=tm["age_group"],
            )
            for tm in t_dict.get("teams", [])
        ]
        team_by_label = {t.label: t for t in teams}

        games = []
        for g_dict in t_dict.get("games", []):
            home = team_by_label.get(g_dict.get("home", ""))
            away = team_by_label.get(g_dict.get("away", ""))
            if home and away:
                games.append(
                    Game(
                        home=home,
                        away=away,
                        parallel_slot=int(g_dict.get("parallel_slot", 0)),
                        round_number=int(g_dict.get("round_number", 0)),
                    )
                )

        date_str = t_dict.get("date", "")
        tournament_date = date.fromisoformat(date_str) if date_str else date.today()

        tournaments.append(
            Tournament(
                date=tournament_date,
                arena=t_dict.get("arena", ""),
                age_group=t_dict.get("age_group", ""),
                teams=teams,
                games=games,
                host_club=t_dict.get("host_club"),
            )
        )

    start_str = d.get("start_date")
    end_str = d.get("end_date")

    return SeasonPlan(
        tournaments=tournaments,
        start_date=date.fromisoformat(start_str) if start_str else None,
        end_date=date.fromisoformat(end_str) if end_str else None,
        diversity_score=float(d.get("diversity_score", 0.0)),
        pairwise_matchup_score=float(d.get("pairwise_matchup_score", 0.0)),
        month_balance_score=float(d.get("month_balance_score", 0.0)),
        arena_counts=dict(d.get("arena_counts", {})),
        team_game_counts=dict(d.get("team_game_counts", {})),
        game_count_spread=int(d.get("game_count_spread", 0)),
        team_last_game_dates={
            k: date.fromisoformat(v) for k, v in d.get("team_last_game_dates", {}).items()
        },
    )


# ---------------------------------------------------------------------------
# CLI entry point — supports: python3 -m tournament_scheduler.pipeline.stage4_export
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Stage 4: multi-format export")
    parser.add_argument("--work-dir", default=".pipeline", help="Pipeline work directory")
    parser.add_argument("--export-dir", default="export", help="Directory for output files")
    cli_args = parser.parse_args()

    from .state import PipelineState, StageName  # noqa: E402

    _state = PipelineState(cli_args.work_dir)
    _plan_ckpt = _state.read_stage(StageName.PLANNING)
    if not _plan_ckpt:
        print("Stage 3 checkpoint not found — run Stage 3 first.", file=sys.stderr)
        sys.exit(1)

    try:
        _result = run(_plan_ckpt, _state, export_dir=cli_args.export_dir)
        files = _result.get("output_files", {})
        print(f"Stage 4 OK — {len(files)} filer eksportert: {', '.join(files.values())}")
        sys.exit(0)
    except Stage4Error as _e:
        print(str(_e), file=sys.stderr)
        sys.exit(1)
