"""Shared helpers for resolving the active pipeline run-log directory."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .state import PipelineState, StageName

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
