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
from .stage4_helpers import _dict_to_plan
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
    timestamped_export: bool = False,
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

    # Store the primary export path (may be flat or timestamped)
    primary_export_path = export_path
    if timestamped_export:
        ts_dir = datetime.now().strftime("%Y-%m-%dT%H%M")
        primary_export_path = export_path / ts_dir
        primary_export_path.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    output_files: dict[str, str] = {}

    # --- Excel ---
    try:
        excel_path = str(primary_export_path / f"{basename}.xlsx")
        rules_report = plan_checkpoint.get("rules_report")
        SeasonPlanExporter().export(plan, excel_path, rules_report=rules_report)
        output_files["excel"] = excel_path
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Excel-eksport feilet: {exc}")

    # --- iCal ---
    try:
        ical_path = str(primary_export_path / f"{basename}.ics")
        ICalExporter().export(plan, ical_path)
        output_files["ical"] = ical_path
    except Exception as exc:  # noqa: BLE001
        errors.append(f"iCal-eksport feilet: {exc}")

    # --- CSV ---
    try:
        csv_path = str(primary_export_path / f"{basename}.csv")
        games_path, overview_path = CsvExporter().export(plan, csv_path)
        output_files["csv_games"] = games_path
        output_files["csv_overview"] = overview_path
    except Exception as exc:  # noqa: BLE001
        errors.append(f"CSV-eksport feilet: {exc}")

    # --- HTML ---
    try:
        html_path = str(primary_export_path / f"{basename}.html")
        # Collect pipeline metadata for metrics section
        pipeline_meta: dict[str, Any] = {}
        try:
            scraping_ckpt = state.read_stage(StageName.SCRAPING)
            if scraping_ckpt and isinstance(scraping_ckpt, dict):
                # read_stage() returns the data dict directly (no wrapper)
                sources = scraping_ckpt.get("sources", [])
                pipeline_meta["source_count"] = len(sources)
                pipeline_meta["total_events"] = sum(s.get("event_count", 0) for s in sources)
                pipeline_meta["blocked"] = scraping_ckpt.get("blocked", [])
                pipeline_meta["date_range"] = f"{cfg.get('start_date','')} &ndash; {cfg.get('end_date','')}"
                updated = scraping_ckpt.get("updated_at", "")
                if updated:
                    from datetime import datetime as _dt
                    try:
                        delta = _dt.now() - _dt.fromisoformat(updated)
                        if delta.total_seconds() < 3600:
                            pipeline_meta["scrape_age"] = f"{int(delta.total_seconds() // 60)}m siden"
                        elif delta.days < 1:
                            pipeline_meta["scrape_age"] = f"{int(delta.total_seconds() // 3600)}t siden"
                        else:
                            pipeline_meta["scrape_age"] = f"{delta.days}d siden"
                    except Exception:
                        pass
        except Exception:
            pass
        # Scrape metadata from cache for navbar
        meta = None
        try:
            from .cache_manager import ScrapedDataCache
            meta = ScrapedDataCache(state.work_dir).read().get("_meta")
        except Exception:
            pass
        HtmlExporter().export(plan, html_path, meta=meta, output_files=output_files, pipeline_meta=pipeline_meta)
        output_files["html"] = html_path
    except Exception as exc:  # noqa: BLE001
        errors.append(f"HTML-eksport feilet: {exc}")

    # --- Spond ---
    try:
        round_length_for_age_group: dict[str, int] = {}
        try:
            config_ckpt = state.read_stage(StageName.CONFIG)
            if isinstance(config_ckpt, dict):
                round_length_for_age_group = dict(config_ckpt.get("round_length_minutes", {}))
        except Exception:
            pass
        spond_path = str(primary_export_path / f"{basename}_spond.xlsx")
        SpondExporter().export(
            plan,
            spond_path,
            round_length_for_age_group=round_length_for_age_group,
        )
        output_files["spond"] = spond_path
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Spond-eksport feilet: {exc}")

    # --- Copy to flat directory for convenience ---
    if timestamped_export:
        import shutil
        for label, path in list(output_files.items()):
            try:
                flat_path = export_path / Path(path).name
                shutil.copy2(path, flat_path)
                output_files[f"{label}_flat"] = str(flat_path)
            except Exception as exc:
                errors.append(f"Kopiering til flat katalog feilet ({label}): {exc}")

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
