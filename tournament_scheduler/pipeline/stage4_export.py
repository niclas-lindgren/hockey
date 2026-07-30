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
import re
import sys
import tempfile
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from ..models import Game, Roster, SeasonPlan, Team, Tournament
from ..arena_conflicts import find_arena_interval_collisions
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
from .input_viewer import generate_html as _generate_input_html
from .activity_viewer import generate_activity_artifacts as _generate_activity_artifacts
from .not_started import NOT_STARTED_MESSAGE, render_not_started_html

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_EXPORT_DIR = "export"
DEFAULT_BASENAME = "season_plan"

# Matches the "%Y-%m-%dT%H%M" directory name this module generates below.
# Callers (e.g. a stage-by-stage orchestrator that picks one export dir up
# front to keep a run's logs and export together) sometimes pass an
# already-timestamped --export-dir. Detecting that here keeps a second,
# nested timestamp from being appended on top of it.
_TIMESTAMP_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{4}$")


def _resolve_build_timestamp(build_timestamp: str | int | float | datetime | None = None) -> datetime:
    """Return the canonical UTC content timestamp for a Stage 4 export.

    ``build_timestamp`` wins when provided. Otherwise ``SOURCE_DATE_EPOCH``
    is honored for reproducible builds, falling back to the current wall
    clock. Naive datetimes/ISO strings are treated as UTC because the value
    describes generated content, not a local operator audit moment.
    """
    raw: str | int | float | datetime | None = build_timestamp
    if raw is None:
        raw = os.environ.get("SOURCE_DATE_EPOCH")

    if raw is None or raw == "":
        return datetime.now(timezone.utc).replace(microsecond=0)

    if isinstance(raw, datetime):
        moment = raw
    elif isinstance(raw, (int, float)):
        moment = datetime.fromtimestamp(float(raw), tz=timezone.utc)
    else:
        value = str(raw).strip()
        if not value:
            return datetime.now(timezone.utc).replace(microsecond=0)
        if re.fullmatch(r"\d+(?:\.\d+)?", value):
            moment = datetime.fromtimestamp(float(value), tz=timezone.utc)
        else:
            try:
                moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise Stage4Error(f"Ugyldig build timestamp '{raw}': {exc}") from exc

    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).replace(microsecond=0)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class Stage4Error(RuntimeError):
    """Raised when Stage 4 export fails."""


def _zip_datetime(build_timestamp: datetime) -> tuple[int, int, int, int, int, int]:
    """Return a ZIP-compatible UTC timestamp tuple.

    ZIP stores local DOS timestamps and cannot represent years before 1980;
    reproducible builds using earlier epochs are clamped to that minimum.
    """
    moment = build_timestamp.astimezone(timezone.utc).replace(microsecond=0)
    if moment.year < 1980:
        moment = moment.replace(year=1980, month=1, day=1, hour=0, minute=0, second=0)
    return (moment.year, moment.month, moment.day, moment.hour, moment.minute, moment.second)


def _normalize_xlsx(path: Path, build_timestamp: datetime) -> None:
    """Normalize an XLSX workbook's embedded and ZIP metadata in place."""
    import openpyxl

    workbook = openpyxl.load_workbook(path)
    workbook.properties.created = build_timestamp.replace(tzinfo=None)
    workbook.properties.modified = build_timestamp.replace(tzinfo=None)
    workbook.save(path)

    fixed_date_time = _zip_datetime(build_timestamp)
    with tempfile.NamedTemporaryFile(delete=False, dir=path.parent, suffix=".xlsx") as handle:
        tmp_path = Path(handle.name)

    try:
        with zipfile.ZipFile(path, "r") as source, zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as dest:
            for name in sorted(source.namelist()):
                original_info = source.getinfo(name)
                info = zipfile.ZipInfo(filename=name, date_time=fixed_date_time)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = original_info.external_attr
                info.comment = original_info.comment
                info.create_system = original_info.create_system
                dest.writestr(info, source.read(name))
        tmp_path.replace(path)
    finally:
        tmp_path.unlink(missing_ok=True)


def _normalize_export_workbooks(primary_export_path: Path, build_timestamp: datetime) -> None:
    for workbook_path in sorted(primary_export_path.rglob("*.xlsx")):
        _normalize_xlsx(workbook_path, build_timestamp)


def _write_not_started_exports(primary_export_path: Path, basename: str, message: str) -> dict[str, str]:
    """Write the normal export surface as small placeholder files."""
    import openpyxl

    primary_export_path.mkdir(parents=True, exist_ok=True)
    output_files: dict[str, str] = {}

    def _write_workbook(path: Path, title: str) -> None:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = title[:31]
        ws.append([message])
        wb.save(path)

    html = render_not_started_html(message)

    excel_path = primary_export_path / f"{basename}.xlsx"
    _write_workbook(excel_path, "Ikke begynt")
    output_files["excel"] = str(excel_path)

    ical_path = primary_export_path / f"{basename}.ics"
    ical_path.write_text(
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//RVV Miniputt//Not Started//NO\r\n"
        "X-WR-CALNAME:Ikke begynt\r\nEND:VCALENDAR\r\n",
        encoding="utf-8",
    )
    output_files["ical"] = str(ical_path)

    csv_path = primary_export_path / f"{basename}.csv"
    csv_path.write_text(f"status\n{message}\n", encoding="utf-8")
    output_files["csv_games"] = str(csv_path)

    overview_path = primary_export_path / f"{basename}_overview.csv"
    overview_path.write_text(f"status\n{message}\n", encoding="utf-8")
    output_files["csv_overview"] = str(overview_path)

    for key, filename in (
        ("input_html", "input.html"),
        ("calendars_html", "calendars.html"),
        ("html", f"{basename}.html"),
        ("html_report", f"{basename}_report.html"),
    ):
        path = primary_export_path / filename
        path.write_text(html, encoding="utf-8")
        output_files[key] = str(path)

    spond_path = primary_export_path / f"{basename}_spond.xlsx"
    _write_workbook(spond_path, "Ikke begynt")
    output_files["spond"] = str(spond_path)

    spond_games_path = primary_export_path / f"{basename}_spond_games.xlsx"
    _write_workbook(spond_games_path, "Ikke begynt")
    output_files["spond_games"] = str(spond_games_path)

    review_dir = primary_export_path / "review_packets"
    review_dir.mkdir(parents=True, exist_ok=True)
    (review_dir / "README.txt").write_text(message + "\n", encoding="utf-8")
    output_files["review_packets"] = str(review_dir)

    return output_files


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
    build_timestamp: str | int | float | datetime | None = None,
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
    canonical_build_timestamp = _resolve_build_timestamp(build_timestamp)

    # Store the primary export path (may be flat or timestamped)
    primary_export_path = export_path
    already_timestamped = bool(_TIMESTAMP_DIR_RE.match(export_path.name))
    if timestamped_export and not already_timestamped:
        ts_dir = canonical_build_timestamp.strftime("%Y-%m-%dT%H%M")
        primary_export_path = export_path / ts_dir
        primary_export_path.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    output_files: dict[str, str] = {}
    effective_config: dict[str, Any] = {}
    try:
        effective_config = load_effective_config(state)
    except Exception:
        effective_config = {}
    generated_at = canonical_build_timestamp.isoformat()
    input_path = str(effective_config.get("input_path") or "input.xlsx")

    if plan_dict.get("placeholder") == "not_started" or (plan_checkpoint.get("not_started") and not plan.tournaments):
        message = str(plan_dict.get("message") or NOT_STARTED_MESSAGE)
        _progress("Genererer tomme ikke-begynt-filer")
        output_files = _write_not_started_exports(primary_export_path, basename, message)
        _normalize_export_workbooks(primary_export_path, canonical_build_timestamp)
        checkpoint = {
            "generated_at": generated_at,
            "input_path": input_path,
            "output_files": output_files,
            "errors": [],
            "not_started": True,
            "message": message,
        }
        state.write_stage(StageName.EXPORT, checkpoint, status=StageStatus.DONE)
        _progress("Eksport ferdig")
        return checkpoint

    round_length_for_age_group: dict[str, int] = dict(effective_config.get("round_length_minutes", {}))
    derived_collisions = find_arena_interval_collisions(plan.tournaments, round_length_for_age_group)
    hard_collisions = derived_collisions or list(plan.arena_day_collisions or [])
    if hard_collisions:
        plan.arena_day_collisions = hard_collisions
        first = hard_collisions[0]
        detail = first.get("message") if isinstance(first, dict) else str(first)
        reason = f"Hard scheduling conflict blocks export: {detail}"
        state.write_stage(
            StageName.EXPORT,
            {"errors": [reason], "arena_day_collisions": hard_collisions},
            status=StageStatus.FAILED,
        )
        if strict:
            raise Stage4Error(reason)
        return {"errors": [reason], "arena_day_collisions": hard_collisions}

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
        pipeline_meta: dict[str, Any] = {
            "generated_at": generated_at,
            "input_path": input_path,
            "input_file": Path(input_path).name,
        }
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
                pipeline_meta["scrape_updated_at"] = updated
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
        # --- Input viewer (input.html) — public overview of registered clubs/teams ---
        # Generated before the calendar viewer so calendars.html's navbar can link to it.
        # Only the whitelisted "Lag" worksheet is read (see input_workbook.PUBLIC_SHEET_WHITELIST).
        # Only generated when Stage 1 actually recorded an input workbook path that exists on
        # disk — deliberately not the "input.xlsx" fallback default used for cosmetic display
        # elsewhere in this function, so callers that skip Stage 1 (e.g. most stage4 tests, or
        # a plan built directly) never accidentally pick up an unrelated input.xlsx from cwd.
        _configured_input_path = effective_config.get("input_path")
        _input_html_path: str | None = None
        if _configured_input_path and os.path.exists(_configured_input_path):
            try:
                _progress("Genererer oversikt over påmeldte lag")
                _generate_input_html(
                    input_path=_configured_input_path,
                    export_dir=str(primary_export_path),
                )
                _input_html_path = str(primary_export_path / "input.html")
                output_files["input_html"] = _input_html_path
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Input-visning feilet: {exc}")

            try:
                start_year = None
                start_date_value = effective_config.get("start_date")
                if isinstance(start_date_value, str) and len(start_date_value) >= 4:
                    start_year = int(start_date_value[:4])
                _progress("Genererer aktivitetskalender")
                activity_files = _generate_activity_artifacts(
                    input_path=_configured_input_path,
                    export_dir=str(primary_export_path),
                    default_year=start_year,
                    generated_at=generated_at,
                )
                if activity_files:
                    output_files.update(activity_files)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Aktivitetskalender feilet: {exc}")
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
            input_html_path=_input_html_path,
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

    try:
        _normalize_export_workbooks(primary_export_path, canonical_build_timestamp)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Normalisering av Excel-filer feilet: {exc}")

    checkpoint: dict[str, Any] = {
        "generated_at": generated_at,
        "input_path": input_path,
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
    parser.add_argument(
        "--timestamped-export",
        dest="timestamped_export",
        action="store_true",
        help="Write exports into a timestamped subfolder of --export-dir",
    )
    parser.add_argument(
        "--no-timestamped-export",
        dest="timestamped_export",
        action="store_false",
        help="Write exports flat into --export-dir",
    )
    parser.add_argument(
        "--build-timestamp",
        default=None,
        help="Canonical content timestamp (ISO-8601 or epoch seconds) for reproducible exports",
    )
    parser.set_defaults(timestamped_export=True)
    cli_args = parser.parse_args()

    from .run_log_paths import append_stage_log_line  # noqa: E402
    from .state import PipelineState, StageName  # noqa: E402

    _state = PipelineState(cli_args.work_dir)
    _plan_ckpt = _state.read_stage(StageName.PLANNING)
    if not _plan_ckpt:
        print("Stage 3 checkpoint not found — run Stage 3 first.", file=sys.stderr)
        sys.exit(1)

    try:
        _result = run(
            _plan_ckpt,
            _state,
            export_dir=cli_args.export_dir,
            timestamped_export=cli_args.timestamped_export,
            build_timestamp=cli_args.build_timestamp,
        )
        files = _result.get("output_files", {})
        print(f"Stage 4 OK — {len(files)} filer eksportert: {', '.join(files.values())}")
        # Resolved after run() so it lands in the export folder run() just used,
        # not the pre-export --export-dir/logs fallback.
        append_stage_log_line(
            _state,
            f"Stage 4 OK: {len(files)} files exported",
            preferred_export_dir=cli_args.export_dir,
        )
        sys.exit(0)
    except Stage4Error as _e:
        append_stage_log_line(_state, f"Stage 4 FAILED: {_e}", preferred_export_dir=cli_args.export_dir)
        print(str(_e), file=sys.stderr)
        sys.exit(1)
