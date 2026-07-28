from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from tournament_scheduler.cli.run_log_archive import archive_latest_run_log


def test_archive_latest_run_log_copies_into_export_root_and_latest_run_dir(tmp_path: Path) -> None:
    work_dir = tmp_path / ".pipeline"
    log_dir = work_dir / "logs"
    log_dir.mkdir(parents=True)

    old_log = log_dir / "run-old.jsonl"
    old_log.write_text("old\n", encoding="utf-8")
    newer_log = log_dir / "run-new.jsonl"
    newer_log.write_text("new\n", encoding="utf-8")

    old_time = datetime.now() - timedelta(minutes=10)
    new_time = datetime.now() - timedelta(minutes=1)
    older_ts = old_time.timestamp()
    newer_ts = new_time.timestamp()
    old_log.touch()
    newer_log.touch()
    import os

    os.utime(old_log, (older_ts, older_ts))
    os.utime(newer_log, (newer_ts, newer_ts))

    export_root = tmp_path / "export"
    run_dir = export_root / "2026-07-27T2230"
    run_dir.mkdir(parents=True)
    (run_dir / "season_plan.xlsx").write_bytes(b"x")

    copied = archive_latest_run_log(["run", "--work-dir", str(work_dir), "--export-dir", str(export_root)])

    assert run_dir / "run-new.jsonl" in copied
    assert export_root / "run-new.jsonl" in copied
    assert (run_dir / "run-new.jsonl").read_text(encoding="utf-8") == "new\n"
    assert (export_root / "run-new.jsonl").read_text(encoding="utf-8") == "new\n"


def test_archive_latest_run_log_skips_when_export_tree_already_has_newer_log(tmp_path: Path) -> None:
    work_dir = tmp_path / ".pipeline"
    log_dir = work_dir / "logs"
    log_dir.mkdir(parents=True)

    legacy_log = log_dir / "run-legacy.jsonl"
    legacy_log.write_text("legacy\n", encoding="utf-8")

    export_root = tmp_path / "export"
    export_run_dir = export_root / "2026-07-27T2230"
    export_run_dir.mkdir(parents=True)
    existing_log = export_run_dir / "run-current.jsonl"
    existing_log.write_text("current\n", encoding="utf-8")

    legacy_time = datetime.now() - timedelta(minutes=5)
    current_time = datetime.now()
    os_import = __import__("os")
    os_import.utime(legacy_log, (legacy_time.timestamp(), legacy_time.timestamp()))
    os_import.utime(existing_log, (current_time.timestamp(), current_time.timestamp()))

    copied = archive_latest_run_log(["run", "--work-dir", str(work_dir), "--export-dir", str(export_root)])

    assert copied == []
    assert existing_log.read_text(encoding="utf-8") == "current\n"
    assert not (export_root / "run-legacy.jsonl").exists()
