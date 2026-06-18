"""RVV CLI log/status reporting helpers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rich.console import Console

_console = Console()

_STAGE_FILES = [
    ("Stage 1 (Config)", "stage1_config.json"),
    ("Stage 2 (Scraping)", "stage2_scraping.json"),
    ("Stage 3 (Planning)", "stage3_planning.json"),
    ("Stage 4 (Export)", "stage4_export.json"),
]
_STAGE_LABELS = {
    "config": "Konfigurasjon",
    "scraping": "Skraping",
    "planning": "Planlegging",
    "export": "Eksport",
}


def _read_checkpoint(work_dir: Path, filename: str) -> dict[str, Any] | None:
    candidates = [filename, "stage3_plan.json"] if filename == "stage3_planning.json" else [filename]
    for candidate in candidates:
        path = work_dir / candidate
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    return None


def _format_duration(ms: int) -> str:
    if ms < 1000:
        return f"{ms}ms"
    if ms < 60000:
        return f"{ms / 1000:.1f}s"
    minutes, remainder = divmod(ms, 60000)
    return f"{minutes}m {round(remainder / 1000)}s"


def _load_jsonl_entries(log_path: Path) -> list[dict[str, Any]]:
    if not log_path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _load_run_history(work_dir: Path) -> list[dict[str, Any]]:
    log_dir = work_dir / "logs"
    if not log_dir.exists():
        return []

    runs: list[dict[str, Any]] = []
    for log_path in sorted(log_dir.glob("run-*.jsonl"), reverse=True):
        run_id = log_path.stem
        meta = None
        for entry in reversed(_load_jsonl_entries(log_path)):
            if entry.get("type") == "run_meta" and entry.get("run_id") == run_id and entry.get("end_time"):
                meta = entry
                break
        runs.append({"run_id": run_id, "log_path": log_path, "meta": meta})
    return runs


def _build_status_text(work_dir: Path) -> str:
    lines = [f"Pipeline work-dir: {work_dir}", ""]
    for label, filename in _STAGE_FILES:
        checkpoint = _read_checkpoint(work_dir, filename)
        if not checkpoint:
            lines.append(f"  {label}: pending (no checkpoint)")
            continue

        status = checkpoint.get("status", "unknown")
        updated = checkpoint.get("updated_at", "")
        stale = checkpoint.get("stale")
        stale_from = checkpoint.get("stale_from", "?")
        stale_suffix = f"  (stale from {stale_from})" if stale else ""
        updated_suffix = f"  ({updated})" if updated else ""
        lines.append(f"  {label}: {status}{stale_suffix}{updated_suffix}")

        data = checkpoint.get("data") or {}
        if label.startswith("Stage 2"):
            blocked = data.get("blocked") or []
            if blocked:
                lines.append(f"    Blokkerte kilder: {', '.join(blocked)}")
        if label.startswith("Stage 3"):
            plan_dict = data.get("plan") if isinstance(data, dict) else None
            if isinstance(plan_dict, dict):
                try:
                    from .plan_critic import count_critic_issues_from_dict
                    n = count_critic_issues_from_dict(plan_dict)
                    if n:
                        lines.append(f"    Critic: {n} issue(s) found — run 'rvv-miniputt critic' for details")
                    else:
                        lines.append("    Critic: no issues")
                except Exception:
                    pass
        if label.startswith("Stage 4"):
            output_files = data.get("output_files") or {}
            for key, path in output_files.items():
                lines.append(f"    {key}: {path}")

    runs = _load_run_history(work_dir)
    if runs:
        lines.extend(["", f"Logs: {work_dir / 'logs'}", f"  Siste {min(3, len(runs))} kjøringer:"])
        for run in runs[:3]:
            lines.append(f"    • {run['run_id']}.jsonl")

    return "\n".join(lines)


def _resolve_run_id(work_dir: Path, requested: str | None) -> str | None:
    if not requested or requested == "latest":
        runs = _load_run_history(work_dir)
        return runs[0]["run_id"] if runs else None
    return requested


def _build_logs_list_text(work_dir: Path, count: int) -> str:
    runs = _load_run_history(work_dir)[:count]
    if not runs:
        return f"Ingen loggførte kjøringer funnet i {work_dir / 'logs'}/"

    lines = [
        "=== Pipeline kjøringshistorie ===",
        f"Logg-katalog: {work_dir / 'logs'}/",
        f"Viser {len(runs)} siste kjøringer",
        "",
        f"{'Kjøring'.ljust(30)} {'Status'.ljust(12)} {'Varighet'.ljust(12)} {'Starter'.ljust(22)}",
        f"{'─' * 30} {'─' * 12} {'─' * 12} {'─' * 22}",
    ]
    for run in runs:
        meta = run["meta"] or {}
        status = meta.get("exit_status", "ukjent")
        duration = _format_duration(meta["duration_ms"]) if meta.get("duration_ms") else "─"
        start = (meta.get("start_time") or "─")[:19].replace("T", " ")
        lines.append(f"{run['run_id'].ljust(30)} {status.ljust(12)} {duration.ljust(12)} {start}")
    return "\n".join(lines)


def _build_logs_show_text(work_dir: Path, run_id: str) -> str:
    log_path = work_dir / "logs" / f"{run_id}.jsonl"
    if not log_path.exists():
        return f"Kjøring {run_id} ikke funnet i {work_dir / 'logs'}/"

    entries = _load_jsonl_entries(log_path)
    run_meta = next((entry for entry in reversed(entries) if entry.get("type") == "run_meta" and entry.get("run_id") == run_id and entry.get("end_time")), None)
    stage_entries = [entry for entry in entries if entry.get("type") == "stage_meta"]
    llm_entries = [entry for entry in entries if entry.get("type") == "llm_interaction"]
    update_entries = [entry for entry in entries if entry.get("type") == "tournament_update"]

    lines = [f"=== Kjørings-detalj: {run_id} ===", f"Logg-fil: {log_path.name}", ""]
    if run_meta:
        lines.append(f"Status:      {run_meta.get('exit_status', 'ukjent')}")
        if run_meta.get("duration_ms") is not None:
            lines.append(f"Varighet:    {_format_duration(run_meta['duration_ms'])}")
        lines.append(f"Start:       {(run_meta.get('start_time') or '─')[:19].replace('T', ' ')}")
        lines.append(f"Slutt:       {(run_meta.get('end_time') or '─')[:19].replace('T', ' ')}")
        commit = (run_meta.get("git_commit") or "─")[:8]
        dirty = " (dirty)" if run_meta.get("git_dirty") else ""
        lines.append(f"Git commit:  {commit}{dirty}")
        lines.append(f"Gjenopptok:  Trinn {run_meta.get('resume_from', '─')}")
        argv = " ".join(
            f"--{key.replace('_', '-')} {value}" for key, value in (run_meta.get("args") or {}).items() if value is not None
        )
        if argv:
            lines.append(f"Argv:        {argv}")
        lines.append("")

    lines.extend([
        "Stadier:",
        f"{'#'.ljust(4)} {'Stage'.ljust(16)} {'Status'.ljust(10)} {'Varighet'.ljust(12)} Feil",
        f"{'─' * 4} {'─' * 16} {'─' * 10} {'─' * 12} {'─' * 20}",
    ])
    for entry in stage_entries:
        index = f"{entry.get('stage_index', '?')}."
        name = _STAGE_LABELS.get(entry.get("stage_name"), entry.get("stage_name", "?"))
        status = entry.get("status")
        icon = "✓" if status == "ok" else "─" if status == "skipped" else "✗"
        duration = _format_duration(entry["duration_ms"]) if entry.get("duration_ms") else "─"
        error = (entry.get("error") or "")[:40]
        lines.append(f"{index.ljust(4)} {name.ljust(16)} {icon.ljust(10)} {duration.ljust(12)} {error}")
        data_volume = entry.get("data_volume") or {}
        if data_volume:
            volume = ", ".join(f"{key}: {value}" for key, value in data_volume.items())
            lines.append(f"    Data: {volume}")

    if llm_entries:
        lines.extend(["", f"LLM-interaksjoner ({len(llm_entries)}):"])
        for entry in llm_entries[:10]:
            confidence = f" (confidence: {entry['confidence']})" if entry.get("confidence") is not None else ""
            tokens = f" [{entry['tokens']} tokens]" if entry.get("tokens") is not None else ""
            lines.append(f"  • {entry.get('stage_name', '?')}: {entry.get('action', '?')}{confidence}{tokens}")
        if len(llm_entries) > 10:
            lines.append(f"  ... og {len(llm_entries) - 10} flere")

    if update_entries:
        lines.extend(["", f"Turneringsoppdateringer ({len(update_entries)}):"])
        for entry in update_entries[:10]:
            op = entry.get("operation", "?")
            label = "Fjern lag" if op == "team_drop" else "Flytt dato" if op == "date_move" else op
            verdict = "✓" if entry.get("success") is True else "✗" if entry.get("success") is False else "?"
            first_line = (entry.get("summary_nb") or "").splitlines()[0][:80]
            lines.append(f"  {verdict} [{entry.get('tournament_id', '?')}] {label}: {first_line}")
        if len(update_entries) > 10:
            lines.append(f"  ... og {len(update_entries) - 10} flere")

    return "\n".join(lines)


def _build_logs_stats_text(work_dir: Path) -> str:
    runs = _load_run_history(work_dir)
    if not runs:
        return f"Ingen loggførte kjøringer funnet i {work_dir / 'logs'}/"

    success_runs = [run for run in runs if (run["meta"] or {}).get("exit_status") == "success"]
    failed_runs = [run for run in runs if (run["meta"] or {}).get("exit_status") == "failure"]
    total_duration = sum((run["meta"] or {}).get("duration_ms", 0) for run in runs)
    average_duration = round(total_duration / len(runs)) if runs else 0

    lines = [
        "=== Pipeline selvforbedrings-statistikk ===",
        "",
        f"Totalt antall kjøringer: {len(runs)}",
        f"Vellykkede:              {len(success_runs)}",
        f"Feil:                    {len(failed_runs)}",
        f"Feilrate:                {round((len(failed_runs) / len(runs)) * 100) if runs else 0}%",
        f"Gjennomsnittlig varighet: {_format_duration(average_duration)}",
        f"Siste kjøring:           {(((runs[0]['meta'] or {}).get('start_time')) or '─')[:10]}",
        "",
    ]

    stage_stats: dict[str, dict[str, int]] = {}
    for run in runs:
        log_path = work_dir / "logs" / f"{run['run_id']}.jsonl"
        for entry in _load_jsonl_entries(log_path):
            if entry.get("type") != "stage_meta" or not entry.get("duration_ms"):
                continue
            stats = stage_stats.setdefault(entry["stage_name"], {"count": 0, "total_ms": 0, "fails": 0})
            stats["count"] += 1
            stats["total_ms"] += int(entry["duration_ms"])
            if entry.get("status") == "failed":
                stats["fails"] += 1

    if stage_stats:
        lines.extend([
            "Stage-statistikk:",
            f"{'Stage'.ljust(20)} {'Kjøringer'.ljust(12)} {'Gj.snitt'.ljust(12)} {'Feil'.ljust(8)} Feilrate",
            f"{'─' * 20} {'─' * 12} {'─' * 12} {'─' * 8} {'─' * 8}",
        ])
        for name, stats in stage_stats.items():
            avg = _format_duration(round(stats['total_ms'] / stats['count']))
            fail_rate = f"{round((stats['fails'] / stats['count']) * 100)}%" if stats["count"] else "0%"
            lines.append(f"{name.ljust(20)} {str(stats['count']).ljust(12)} {avg.ljust(12)} {str(stats['fails']).ljust(8)} {fail_rate}")
        lines.append("")

    recent_runs = [run for run in runs[:5] if (run["meta"] or {}).get("duration_ms")]
    if len(recent_runs) >= 2:
        lines.append("Varighetstrend (siste 5 kjøringer):")
        for run in recent_runs:
            meta = run["meta"] or {}
            lines.append(f"  {(meta.get('start_time') or '??')[:10]}  {_format_duration(meta['duration_ms'])}  ({meta.get('exit_status', 'ukjent')})")
        first = (recent_runs[-1]["meta"] or {}).get("duration_ms", 0)
        last = (recent_runs[0]["meta"] or {}).get("duration_ms", 0)
        if first and last:
            pct = round(((last - first) / first) * 100)
            arrow = "↓" if pct < -5 else "↑" if pct > 5 else "→"
            lines.append(f"  Trend: {arrow} {abs(pct)}% ({_format_duration(first)} → {_format_duration(last)})")

    return "\n".join(lines)


def _cmd_status(args: argparse.Namespace) -> int:
    _console.print(_build_status_text(Path(args.work_dir)))
    return 0


def _cmd_logs(args: argparse.Namespace) -> int:
    work_dir = Path(args.work_dir)
    subcommand = getattr(args, "logs_command", "list") or "list"
    if subcommand == "show":
        run_id = _resolve_run_id(work_dir, getattr(args, "run_id", None))
        if not run_id:
            _console.print(f"Ingen loggførte kjøringer funnet i {work_dir / 'logs'}/")
            return 0
        _console.print(_build_logs_show_text(work_dir, run_id))
        return 0
    if subcommand == "stats":
        _console.print(_build_logs_stats_text(work_dir))
        return 0

    count = getattr(args, "count", 10) or 10
    _console.print(_build_logs_list_text(work_dir, count))
    return 0
