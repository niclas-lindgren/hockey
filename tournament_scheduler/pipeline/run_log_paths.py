"""Shared helpers for resolving the active pipeline run-log directory."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .state import PipelineState, StageName

STAGE_LOG_FILENAME = "stage_run.log"

# Prefer file outputs first so we land in the actual Stage 4 export folder.
_PREFERRED_OUTPUT_KEYS = (
    "excel",
    "html_report",
    "html",
    "spond",
    "spond_games",
    "ical",
    "csv_games",
    "csv_overview",
    "calendars_html",
    "review_packets",
)


def _export_dir_from_output_files(output_files: Mapping[str, Any]) -> Path | None:
    for key in _PREFERRED_OUTPUT_KEYS:
        path = output_files.get(key)
        if not path:
            continue
        try:
            return Path(path).expanduser().resolve().parent
        except Exception:
            candidate = Path(path).expanduser()
            return candidate.parent if candidate.parent != Path("") else None

    for path in output_files.values():
        if not path:
            continue
        try:
            return Path(path).expanduser().resolve().parent
        except Exception:
            candidate = Path(path).expanduser()
            return candidate.parent if candidate.parent != Path("") else None

    return None


def resolve_active_run_log_dir(
    state: PipelineState,
    *,
    preferred_export_dir: str | Path | None = None,
) -> Path:
    """Return the directory where the active run's logs should live.

    Priority:
    1. Stage 4 ``output_files`` parent directory when available.
    2. An explicit export directory hint from the caller.
    3. The legacy ``<work_dir>/logs`` fallback only when no export context exists.
    """

    try:
        envelope = state.read_envelope(StageName.EXPORT)
        # A stage invalidated by an upstream change (new run, changed input,
        # etc.) keeps its old `data` in place — only `status`/`stale` change
        # — so an unstaled "done" check is required or this happily reuses
        # a previous run's export folder for the whole run before its own
        # Stage 4 has produced fresh output_files.
        if envelope.get("status") == "done" and not envelope.get("stale"):
            output_files = (envelope.get("data") or {}).get("output_files")
            if isinstance(output_files, dict):
                resolved = _export_dir_from_output_files(output_files)
                if resolved is not None:
                    return resolved
    except Exception:
        pass

    if preferred_export_dir is not None:
        export_dir = Path(preferred_export_dir)
        if not export_dir.is_absolute():
            export_dir = Path.cwd() / export_dir
        return export_dir

    return Path(state.work_dir) / "logs"


def append_stage_log_line(
    state: PipelineState,
    message: str,
    *,
    preferred_export_dir: str | Path | None = None,
) -> Path:
    """Append one timestamped line to the active run's human-readable log.

    Each of the four stage scripts writes here from its own ``__main__``
    entry point, so a stage-by-stage session (e.g. an agent invoking each
    stage as its own subprocess per ``run.md``, instead of going through
    ``rvv-miniputt run``) still leaves a readable trail for debugging —
    that path previously produced no log output at all, since only the
    ``operator run`` orchestration wrote ``pipeline_run_*.log``.

    Uses the same directory resolution as the rest of the export-folder
    log routing: before Stage 4 has produced output this lands in
    ``<work_dir>/logs/``, and once Stage 4 has run it moves to the export
    timestamp folder, matching where ``log_update``/``log_cancellation``
    already write. A run's log can therefore legitimately span both
    locations — that mirrors existing behavior rather than introducing a
    new split.
    """
    log_dir = resolve_active_run_log_dir(state, preferred_export_dir=preferred_export_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / STAGE_LOG_FILENAME
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")
    return log_path
