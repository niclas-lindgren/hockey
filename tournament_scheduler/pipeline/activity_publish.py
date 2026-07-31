"""Activity-calendar-only export preparation for GitHub Pages.

The normal Pages publisher replaces ``/latest/`` with a complete sanitized
snapshot.  This helper prepares such a complete snapshot when the only new
content is the public activity calendar: it copies the currently published
``gh-pages:latest/`` files into a staging export directory, then overwrites the
activity artifacts from the selected year-wheel workbook.  The staged directory
can then go through the existing sanitizer/approval/publish flow without
silently deleting the season-plan pages.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .activity_viewer import generate_activity_artifacts
from .input_workbook import WorkbookInputError

_GIT_TIMEOUT_SECONDS = 120


class ActivityPublishError(RuntimeError):
    """Raised when an activity publish staging snapshot cannot be prepared."""


def default_activity_run_id(now: datetime | None = None) -> str:
    """Return a stable run id prefix for activity-calendar publishes."""
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)
    return f"activities-{moment.strftime('%Y%m%dT%H%M%SZ')}"


def fetch_pages_branch(*, repo_dir: str = ".", remote: str = "origin", branch: str = "gh-pages") -> None:
    """Fetch the Pages branch into its remote-tracking ref before staging.

    An explicit refspec is used because ``git fetch origin gh-pages`` only
    guarantees ``FETCH_HEAD``. GitHub Actions normally checks out a detached
    commit and therefore has no local ``gh-pages`` branch. Keeping
    ``refs/remotes/<remote>/<branch>`` current gives snapshot staging a stable,
    unambiguous source ref.
    """
    refspec = f"+refs/heads/{branch}:refs/remotes/{remote}/{branch}"
    proc = subprocess.run(
        ["git", "fetch", remote, refspec],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT_SECONDS,
    )
    if proc.returncode != 0:
        raise ActivityPublishError(
            f"Kunne ikke hente {remote}/{branch} før aktivitetskalender-publisering: {proc.stderr.strip()}"
        )


def _resolve_pages_ref(*, repo_dir: str, branch: str) -> str | None:
    """Resolve a usable commit ref for the Pages branch.

    Local development commonly has a local ``gh-pages`` branch, while GitHub
    Actions normally only has ``origin/gh-pages``. ``FETCH_HEAD`` is retained
    as a final compatibility fallback for callers using a custom fetch step.
    """
    candidates = (branch, f"origin/{branch}", "FETCH_HEAD")
    for candidate in candidates:
        proc = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
        if proc.returncode == 0:
            return candidate
    return None


def copy_latest_snapshot(
    *,
    repo_dir: str = ".",
    branch: str = "gh-pages",
    destination_dir: str | Path,
) -> int:
    """Copy files from the resolved Pages ref's ``latest/`` into destination.

    ``latest/_meta.json`` is intentionally skipped; the publish step writes a
    fresh fingerprint for the new complete bundle.
    """
    dest = Path(destination_dir)
    dest.mkdir(parents=True, exist_ok=True)

    pages_ref = _resolve_pages_ref(repo_dir=repo_dir, branch=branch)
    if pages_ref is None:
        return 0

    tree_proc = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", pages_ref, "--", "latest"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT_SECONDS,
    )
    if tree_proc.returncode != 0:
        return 0

    copied = 0
    for branch_path in sorted(line.strip() for line in tree_proc.stdout.splitlines() if line.strip()):
        if branch_path == "latest/_meta.json":
            continue
        if not branch_path.startswith("latest/"):
            continue
        relative = branch_path[len("latest/"):]
        if not relative:
            continue
        show_proc = subprocess.run(
            ["git", "show", f"{pages_ref}:{branch_path}"],
            cwd=repo_dir,
            capture_output=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
        if show_proc.returncode != 0:
            raise ActivityPublishError(
                f"Kunne ikke lese {pages_ref}:{branch_path}: "
                f"{show_proc.stderr.decode('utf-8', errors='replace').strip()}"
            )
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(show_proc.stdout)
        copied += 1
    return copied


def prepare_activity_latest_export(
    *,
    input_path: str,
    export_dir: str | Path,
    repo_dir: str = ".",
    branch: str = "gh-pages",
    default_year: int | None = None,
    generated_at: str | None = None,
    include_latest_base: bool = True,
    require_latest_base: bool = True,
) -> dict[str, Any]:
    """Prepare a full Pages export snapshot with refreshed activity artifacts.

    Returns a dictionary with ``export_dir``, ``base_file_count`` and
    ``activity_files``.  The caller should publish ``export_dir`` using the
    normal operator publish path so sanitization, approval, fingerprinting and
    verification still apply.
    """
    export_path = Path(export_dir)
    if export_path.exists():
        shutil.rmtree(export_path)
    export_path.mkdir(parents=True, exist_ok=True)

    base_file_count = 0
    if include_latest_base:
        base_file_count = copy_latest_snapshot(repo_dir=repo_dir, branch=branch, destination_dir=export_path)
        if require_latest_base and base_file_count == 0:
            raise ActivityPublishError(
                f"Fant ingen eksisterende /latest/-snapshot på branch '{branch}' eller dens remote-tracking ref. "
                "Avbryter for å unngå å publisere bare aktivitetskalenderen og slette andre sider."
            )

    activity_files = generate_activity_artifacts(
        input_path=input_path,
        export_dir=str(export_path),
        default_year=default_year,
        generated_at=generated_at,
    )
    if activity_files is None:
        raise WorkbookInputError(
            f"Fant ingen støttet aktivitetsfane i '{input_path}' "
            "(forventet f.eks. 'Aktiviteter' eller 'Årshjul')."
        )

    return {
        "export_dir": str(export_path),
        "base_file_count": base_file_count,
        "activity_files": activity_files,
    }
