"""Regression tests for independent GitHub Pages content preservation."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tournament_scheduler.pipeline.pages_publish import diff_latest, publish, rollback_to_run


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def _init_repo(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(["init", "--bare", "-b", "main"], cwd=remote)

    local = tmp_path / "local"
    local.mkdir()
    _git(["init", "-b", "main"], cwd=local)
    _git(["config", "user.email", "test@example.com"], cwd=local)
    _git(["config", "user.name", "Test"], cwd=local)
    (local / "README.md").write_text("hello\n", encoding="utf-8")
    _git(["add", "README.md"], cwd=local)
    _git(["commit", "-m", "initial"], cwd=local)
    _git(["remote", "add", "origin", str(remote)], cwd=local)
    _git(["push", "origin", "main"], cwd=local)
    return local


def _bundle(root: Path, *, season: str, include_independent: bool = False) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "season_plan.html").write_text(season, encoding="utf-8")
    if include_independent:
        (root / "activities").mkdir()
        (root / "activities" / "index.html").write_text("activities", encoding="utf-8")
        (root / "activities.json").write_text("{}", encoding="utf-8")
        (root / "registered-teams").mkdir()
        (root / "registered-teams" / "pameldte-lag.html").write_text(
            "registrations", encoding="utf-8"
        )


def _worktree(local: Path, destination: Path) -> None:
    _git(["worktree", "add", str(destination), "gh-pages"], cwd=local)


def test_season_publish_preserves_independent_pages_and_snapshots_them(tmp_path):
    local = _init_repo(tmp_path)
    first = tmp_path / "first"
    _bundle(first, season="v1", include_independent=True)
    assert publish(export_dir=str(first), run_id="run-1", repo_dir=str(local), push=False).status == "ok"

    second = tmp_path / "second"
    _bundle(second, season="v2")
    assert publish(export_dir=str(second), run_id="run-2", repo_dir=str(local), push=False).status == "ok"

    check = tmp_path / "check"
    _worktree(local, check)
    assert (check / "latest" / "season_plan.html").read_text() == "v2"
    assert (check / "latest" / "activities" / "index.html").read_text() == "activities"
    assert (check / "latest" / "activities.json").read_text() == "{}"
    assert (
        check / "latest" / "registered-teams" / "pameldte-lag.html"
    ).read_text() == "registrations"
    assert (
        check / "runs" / "run-2" / "registered-teams" / "pameldte-lag.html"
    ).read_text() == "registrations"


def test_diff_does_not_preview_independent_pages_as_removals(tmp_path):
    local = _init_repo(tmp_path)
    first = tmp_path / "first"
    _bundle(first, season="v1", include_independent=True)
    (first / "obsolete.txt").write_text("remove me", encoding="utf-8")
    publish(export_dir=str(first), run_id="run-1", repo_dir=str(local), push=False)

    second = tmp_path / "second"
    _bundle(second, season="v2")
    preview = diff_latest(str(second), repo_dir=str(local), branch="gh-pages")

    assert preview["remove"] == ["latest/obsolete.txt"]


def test_rollback_to_legacy_run_keeps_independent_pages(tmp_path):
    local = _init_repo(tmp_path)
    legacy = tmp_path / "legacy"
    _bundle(legacy, season="legacy")
    publish(export_dir=str(legacy), run_id="legacy", repo_dir=str(local), push=False)

    current = tmp_path / "current"
    _bundle(current, season="current", include_independent=True)
    publish(export_dir=str(current), run_id="current", repo_dir=str(local), push=False)

    result = rollback_to_run(run_id="legacy", repo_dir=str(local), push=False)
    assert result.status == "ok"

    check = tmp_path / "check-rollback"
    _worktree(local, check)
    assert (check / "latest" / "season_plan.html").read_text() == "legacy"
    assert (
        check / "latest" / "registered-teams" / "pameldte-lag.html"
    ).read_text() == "registrations"
