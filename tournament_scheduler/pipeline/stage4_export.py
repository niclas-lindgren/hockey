"""Stage 4 — multi-format export (Excel, iCal, CSV).

Reads the Stage 3 plan checkpoint, reconstructs a :class:`SeasonPlan` from it,
and writes three output files:

- ``<export_dir>/season_plan.xlsx``   — Excel workbook via :class:`SeasonPlanExporter`
- ``<export_dir>/season_plan.ics``    — iCal feed via :class:`ICalExporter`
- ``<export_dir>/season_plan.csv``    — flat game CSV + ``_overview.csv`` via :class:`CsvExporter`
- ``<export_dir>/season_plan.html``   — interactive HTML overview via :class:`~tournament_scheduler.html.html_exporter.HtmlExporter`
- ``<export_dir>/season_plan_report.html``   — companion diagnostics report with fairness / travel / hosting summaries
- ``<export_dir>/season_plan_spond_games.xlsx`` — printable tournament-by-tournament schedule attachment for Spond
- ``<export_dir>/review_packets/`` — per-club approval folders with review workbook, Spond import, schedule attachment, and response template

File paths are written to the Stage 4 checkpoint.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ..models import Game, Roster, SeasonPlan, Team, Tournament
from ..excel.plan_exporter import SeasonPlanExporter
from ..ical.ical_exporter import ICalExporter
from ..csv.csv_exporter import CsvExporter
from ..html.html_exporter import HtmlExporter
from ..review.review_packet_exporter import ReviewPacketExporter
from ..spond.spond_exporter import SpondExporter
from .stage1_config import load_effective_config
from .state import PipelineState, StageName, StageStatus
from .stage4_helpers import _dict_to_plan
from .calendar_viewer import generate_html as _generate_calendars_html

logger = logging.getLogger(__name__)

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
    timestamped_export: bool = True,
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
    def _progress(message: str) -> None:
        print(f"[progress] {message}", file=sys.stdout, flush=True)

    state.write_stage(StageName.EXPORT, {}, status=StageStatus.RUNNING)
    _progress("Klarmaker eksport: laster plan og forbereder filer")

    plan_dict = plan_checkpoint.get("plan", {})
    if not plan_dict:
        reason = "Ingen plan funnet i Stage 3 checkpoint — kjør Stage 3 først."
        state.write_stage(StageName.EXPORT, {}, status=StageStatus.FAILED)
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
    effective_config: dict[str, Any] = {}
    try:
        effective_config = load_effective_config(state)
    except Exception:
        effective_config = {}
    round_length_for_age_group: dict[str, int] = dict(effective_config.get("round_length_minutes", {}))
    configured_age_groups = list(dict.fromkeys(effective_config.get("age_groups", [])))
    if not configured_age_groups and not effective_config.get("age_groups_from_input", False):
        configured_age_groups = sorted({t.age_group for t in plan.tournaments})

    # --- Excel ---
    try:
        _progress("Eksporterer Excel-arbeidsbok")
        excel_path = str(primary_export_path / f"{basename}.xlsx")
        rules_report = plan_checkpoint.get("rules_report")
        SeasonPlanExporter().export(
            plan,
            excel_path,
            rules_report=rules_report,
            round_length_for_age_group=round_length_for_age_group,
        )
        output_files["excel"] = excel_path
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Excel-eksport feilet: {exc}")

    # --- iCal ---
    try:
        _progress("Eksporterer iCal-feed")
        ical_path = str(primary_export_path / f"{basename}.ics")
        ICalExporter(round_length_for_age_group=round_length_for_age_group).export_tournament_summary(plan, ical_path)
        output_files["ical"] = ical_path
    except Exception as exc:  # noqa: BLE001
        errors.append(f"iCal-eksport feilet: {exc}")

    # --- CSV ---
    try:
        _progress("Eksporterer CSV-filer")
        csv_path = str(primary_export_path / f"{basename}.csv")
        games_path, overview_path = CsvExporter().export(plan, csv_path)
        output_files["csv_games"] = games_path
        output_files["csv_overview"] = overview_path
    except Exception as exc:  # noqa: BLE001
        errors.append(f"CSV-eksport feilet: {exc}")

    # --- HTML ---
    try:
        _progress("Genererer HTML-rapport")
        html_path = str(primary_export_path / f"{basename}.html")
        # Collect pipeline metadata for metrics section
        pipeline_meta: dict[str, Any] = {}
        try:
            scraping_envelope = state.read_envelope(StageName.SCRAPING)
        except Exception as exc:
            logger.warning("Kunne ikke lese scraping-checkpoint for rapporten: %s", exc)
            scraping_envelope = None
        scraping_ckpt = scraping_envelope.get("data", {}) if scraping_envelope else None
        if scraping_ckpt and isinstance(scraping_ckpt, dict):
            # read_envelope() returns the full wrapper so updated_at is accessible at top level
            sources = scraping_ckpt.get("sources", [])
            pipeline_meta["source_count"] = len(sources)
            pipeline_meta["total_events"] = sum(s.get("event_count", 0) for s in sources)
            pipeline_meta["blocked"] = scraping_ckpt.get("blocked", [])
            pipeline_meta["date_range"] = (
                f"{effective_config.get('start_date', '')} &ndash; {effective_config.get('end_date', '')}"
            )
            pipeline_meta["age_groups"] = configured_age_groups
            updated = scraping_envelope.get("updated_at", "") if scraping_envelope else ""
            if updated:
                from datetime import datetime as _dt, timezone as _tz
                try:
                    delta = _dt.now(tz=_tz.utc) - _dt.fromisoformat(updated)
                    if delta.total_seconds() < 3600:
                        pipeline_meta["scrape_age"] = f"{int(delta.total_seconds() // 60)}m siden"
                    elif delta.days < 1:
                        pipeline_meta["scrape_age"] = f"{int(delta.total_seconds() // 3600)}t siden"
                    else:
                        pipeline_meta["scrape_age"] = f"{delta.days}d siden"
                except Exception as exc:
                    logger.warning(
                        "Kunne ikke tolke updated_at='%s' i scraping-checkpoint: %s",
                        updated,
                        exc,
                    )
        # Scrape metadata from cache for navbar
        meta = None
        _scrape_cache_data: dict[str, Any] = {}
        try:
            from .cache_manager import ScrapedDataCache
            _scrape_cache_data = ScrapedDataCache(state.work_dir).read()
            meta = _scrape_cache_data.get("_meta")
        except Exception as exc:
            logger.warning("Kunne ikke lese scrape-cache for rapporten: %s", exc)
        # --- Calendar viewer (calendars.html) ---
        # Generate before HtmlExporter so calendars_path can be passed in and the navbar can link to it.
        # Only generate when scrape data exists — without it the file would be empty and the navbar link would be broken.
        # total_events/source_count are top-level keys in the cache, not inside _meta.
        _calendars_path: str | None = None
        if _scrape_cache_data.get("total_events", 0) > 0 or _scrape_cache_data.get("source_count", 0) > 0:
            try:
                _progress("Genererer kalenderoversikt")
                _generate_calendars_html(
                    work_dir=str(state.work_dir),
                    export_dir=str(primary_export_path),
                )
                _calendars_path = str(primary_export_path / "calendars.html")
                output_files["calendars_html"] = _calendars_path
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Kalendervisning feilet: {exc}")
        HtmlExporter().export(
            plan,
            html_path,
            meta=meta,
            output_files=output_files,
            pipeline_meta=pipeline_meta,
            age_groups=configured_age_groups,
            calendars_path=_calendars_path,
        )
        output_files["html"] = html_path
        output_files["html_report"] = str(Path(html_path).with_name(f"{Path(html_path).stem}_report{Path(html_path).suffix}"))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"HTML-eksport feilet: {exc}")

    # --- Spond ---
    try:
        _progress("Genererer Spond-eksport")
        spond_path = str(primary_export_path / f"{basename}_spond.xlsx")
        schedule_path = str(primary_export_path / f"{basename}_spond_games.xlsx")
        exporter = SpondExporter()
        exporter.export(
            plan,
            spond_path,
            round_length_for_age_group=round_length_for_age_group,
        )
        exporter.export_schedule_attachment(
            plan,
            schedule_path,
            round_length_for_age_group=round_length_for_age_group,
        )
        output_files["spond"] = spond_path
        output_files["spond_games"] = schedule_path
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Spond-eksport feilet: {exc}")

    # --- Per-club review packets ---
    try:
        _progress("Genererer klubbreview-pakker")
        review_dir = primary_export_path / "review_packets"
        clubs = sorted({team.club for tournament in plan.tournaments for team in tournament.teams})
        ReviewPacketExporter().export(
            plan,
            review_dir,
            clubs=clubs,
            round_length_for_age_group=round_length_for_age_group,
        )
        output_files["review_packets"] = str(review_dir)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Review-pakker feilet: {exc}")

    checkpoint: dict[str, Any] = {
        "output_files": output_files,
        "errors": errors,
    }

    if errors and strict:
        state.write_stage(StageName.EXPORT, checkpoint, status=StageStatus.FAILED)
        _progress("Eksport feilet")
        raise Stage4Error("\n".join(errors))

    status = StageStatus.DONE if not errors else StageStatus.FAILED
    state.write_stage(StageName.EXPORT, checkpoint, status=status)
    _progress("Eksport ferdig")
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
