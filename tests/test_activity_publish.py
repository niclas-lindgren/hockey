"""Tests for activity-calendar Pages staging."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import openpyxl

from tournament_scheduler.pipeline.activity_publish import prepare_activity_latest_export


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _write_activity_workbook(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Årshjul"
    ws.append(["Dato", "Aktivitet"])
    ws.append(["2026-01-17", "RS U15"])
    wb.save(path)


def _repo_with_pages_latest(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "--allow-empty", "-m", "initial")
    main_branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    _git(repo, "checkout", "--orphan", "gh-pages")
    for child in repo.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    latest = repo / "latest"
    latest.mkdir()
    (latest / "season_plan.html").write_text("<h1>Current plan</h1>", encoding="utf-8")
    (latest / "_meta.json").write_text('{"old": true}', encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "pages")
    _git(repo, "checkout", main_branch)


class TestActivityPublish:
    def test_prepare_activity_latest_export_overlays_current_latest_snapshot(self, tmp_path):
        repo = tmp_path / "repo"
        _repo_with_pages_latest(repo)
        workbook = tmp_path / "activities.xlsx"
        _write_activity_workbook(workbook)
        export_dir = tmp_path / "staged"

        result = prepare_activity_latest_export(
            input_path=str(workbook),
            export_dir=export_dir,
            repo_dir=str(repo),
            branch="gh-pages",
        )

        assert result["base_file_count"] == 1
        assert (export_dir / "season_plan.html").read_text(encoding="utf-8") == "<h1>Current plan</h1>"
        assert not (export_dir / "_meta.json").exists()
        assert (export_dir / "activities.json").exists()
        assert (export_dir / "activities" / "index.html").exists()
        assert "RS U15" in (export_dir / "activities.json").read_text(encoding="utf-8")

    def test_prepare_activity_latest_export_uses_remote_tracking_pages_ref(self, tmp_path):
        source = tmp_path / "source"
        _repo_with_pages_latest(source)

        bare = tmp_path / "remote.git"
        subprocess.run(
            ["git", "clone", "--bare", str(source), str(bare)],
            check=True,
            capture_output=True,
            text=True,
        )

        checkout = tmp_path / "checkout"
        subprocess.run(
            ["git", "clone", str(bare), str(checkout)],
            check=True,
            capture_output=True,
            text=True,
        )
        assert subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", "gh-pages^{commit}"],
            cwd=checkout,
            capture_output=True,
        ).returncode != 0
        assert subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", "origin/gh-pages^{commit}"],
            cwd=checkout,
            capture_output=True,
        ).returncode == 0

        workbook = tmp_path / "activities.xlsx"
        _write_activity_workbook(workbook)
        export_dir = tmp_path / "staged-remote"

        result = prepare_activity_latest_export(
            input_path=str(workbook),
            export_dir=export_dir,
            repo_dir=str(checkout),
            branch="gh-pages",
        )

        assert result["base_file_count"] == 1
        assert (export_dir / "season_plan.html").exists()
        assert (export_dir / "activities" / "index.html").exists()
