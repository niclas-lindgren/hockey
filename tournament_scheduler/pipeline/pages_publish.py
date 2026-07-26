"""Operator-driven GitHub Pages publishing (issue #17).

Lets the operator publish an already-exported season plan (Stage 4 output)
to a dedicated ``gh-pages`` branch without running the planning pipeline in
GitHub Actions. This module only moves already-produced files into a Pages
branch and commits/pushes them — it does not generate or sanitize content
(see issue #18 for a sanitized public bundle) and does not gate on human
approval itself (see issue #19); the ``publish_pages`` operator action it is
registered under is marked ``external``/``requires_approval`` like every
other action that writes outside the workspace (see
``pipeline/operator_action.py``).

Publish layout on the ``gh-pages`` branch::

    /index.html          redirect to /latest/
    /.nojekyll
    /latest/...           overwritten on every publish
    /runs/<run-id>/...    written once per run id, never removed

Implementation notes:

- A short-lived ``git worktree`` is used so publishing never touches the
  caller's current checkout (working tree, index, or branch).
- History is preserved: pushes are always plain fast-forward pushes, never
  ``--force``. A local branch that has diverged from its remote is reported
  as a failure rather than silently overwritten.
- Every operation returns a :class:`~.capability_result.CapabilityResult`
  instead of raising, matching every other operator action executor.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .capability_result import CapabilityResult

_GIT_TIMEOUT_SECONDS = 120

_ROOT_INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=latest/">
<title>RVV Miniputt season plan</title>
</head>
<body>
<p>Redirecting to the <a href="latest/">latest published season plan</a>.</p>
</body>
</html>
"""


class PagesPublishError(RuntimeError):
    """A git operation needed to set up the Pages branch could not proceed.

    Raised only for setup problems (e.g. not a git repo at all); everything
    past that point is reported as a :class:`CapabilityResult` instead, so
    callers never need to catch this directly.
    """


def _git(args: list[str], *, cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT_SECONDS,
    )


def _require_git_repo_root(repo_dir: str) -> str:
    proc = _git(["rev-parse", "--show-toplevel"], cwd=repo_dir)
    if proc.returncode != 0:
        raise PagesPublishError(
            f"'{repo_dir}' er ikke inne i et git-repo: {proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def _remote_url(repo_root: str, remote: str) -> str:
    proc = _git(["config", "--get", f"remote.{remote}.url"], cwd=repo_root)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _parse_owner_repo(remote_url: str) -> tuple[str, str] | None:
    """Extract ``(owner, repo)`` from an SSH or HTTPS GitHub remote URL."""
    remote_url = remote_url.strip()
    match = re.match(r"^git@[^:]+:([^/]+)/(.+?)(\.git)?/?$", remote_url)
    if match is None:
        match = re.match(r"^https?://[^/]+/([^/]+)/(.+?)(\.git)?/?$", remote_url)
    if match is None:
        return None
    return match.group(1), match.group(2)


def _pages_urls(owner: str, repo: str, run_id: str) -> tuple[str, str]:
    base = f"https://{owner}.github.io/{repo}"
    return f"{base}/latest/", f"{base}/runs/{run_id}/"


def _branch_exists_locally(repo_root: str, branch: str) -> bool:
    proc = _git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=repo_root)
    return proc.returncode == 0


def _branch_exists_on_remote(repo_root: str, remote: str, branch: str) -> bool:
    proc = _git(["ls-remote", "--exit-code", "--heads", remote, branch], cwd=repo_root)
    return proc.returncode == 0


def _copy_bundle(export_dir: Path, dest_dir: Path) -> None:
    """Copy *export_dir*'s contents into *dest_dir*, overwriting it wholesale.

    Adds an ``index.html`` when the bundle doesn't already have one (falling
    back to a copy of ``season_plan.html``) so the directory resolves on its
    own as a Pages URL.
    """
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    shutil.copytree(export_dir, dest_dir)
    index_path = dest_dir / "index.html"
    if not index_path.exists():
        season_html = dest_dir / "season_plan.html"
        if season_html.exists():
            shutil.copyfile(season_html, index_path)
        else:
            index_path.write_text(
                "<!doctype html><title>Season plan</title><p>Ingen HTML-eksport funnet.</p>",
                encoding="utf-8",
            )


def _write_root_index(branch_root: Path) -> None:
    (branch_root / "index.html").write_text(_ROOT_INDEX_HTML, encoding="utf-8")
    (branch_root / ".nojekyll").write_text("", encoding="utf-8")


def publish(
    *,
    export_dir: str,
    run_id: str,
    repo_dir: str = ".",
    branch: str = "gh-pages",
    remote: str = "origin",
    push: bool = True,
) -> CapabilityResult:
    """Publish *export_dir* (a Stage 4 export bundle) to the Pages branch.

    Writes the bundle under both ``/latest/`` (overwritten every call) and
    ``/runs/<run_id>/`` (written once per run id) on *branch*, commits the
    result with a plain (non-orphan-clobbering, non-force) commit, and
    pushes it to *remote* unless ``push=False``. Returns a
    :class:`CapabilityResult` describing the outcome — never raises for
    anything past initial argument/repo validation.
    """
    export_path = Path(export_dir)
    if not export_path.is_dir() or not any(export_path.iterdir()):
        return CapabilityResult.failed(
            f"Eksportmappe '{export_dir}' finnes ikke eller er tom — kjør Stage 4-eksport først.",
            capability="pages_publish",
        )

    try:
        repo_root = _require_git_repo_root(repo_dir)
    except PagesPublishError as exc:
        return CapabilityResult.failed(str(exc), capability="pages_publish")

    owner_repo = _parse_owner_repo(_remote_url(repo_root, remote))

    tmp_dir = tempfile.mkdtemp(prefix="rvv-pages-")
    worktree_added = False
    try:
        if push:
            _git(["fetch", remote, branch], cwd=repo_root)

        local_exists = _branch_exists_locally(repo_root, branch)
        remote_exists = push and _branch_exists_on_remote(repo_root, remote, branch)

        if not local_exists and remote_exists:
            proc = _git(["branch", "--track", branch, f"{remote}/{branch}"], cwd=repo_root)
            if proc.returncode != 0:
                return CapabilityResult.failed(
                    f"Kunne ikke opprette lokal branch '{branch}': {proc.stderr.strip()}",
                    capability="pages_publish",
                )
            local_exists = True

        if local_exists:
            proc = _git(["worktree", "add", tmp_dir, branch], cwd=repo_root)
            if proc.returncode != 0:
                return CapabilityResult.failed(
                    f"Kunne ikke sette opp arbeidskatalog for '{branch}': {proc.stderr.strip()}",
                    capability="pages_publish",
                )
            worktree_added = True
            if remote_exists:
                ff_proc = _git(["merge", "--ff-only", f"{remote}/{branch}"], cwd=tmp_dir)
                if ff_proc.returncode != 0:
                    return CapabilityResult.failed(
                        f"Lokal '{branch}' har divergert fra {remote}/{branch} og kan ikke "
                        f"fast-forwardes automatisk — løs manuelt før publisering.",
                        capability="pages_publish",
                    )
        else:
            proc = _git(["worktree", "add", "--detach", tmp_dir, "HEAD"], cwd=repo_root)
            if proc.returncode != 0:
                return CapabilityResult.failed(
                    f"Kunne ikke opprette midlertidig arbeidskatalog: {proc.stderr.strip()}",
                    capability="pages_publish",
                )
            worktree_added = True
            orphan_proc = _git(["checkout", "--orphan", branch], cwd=tmp_dir)
            if orphan_proc.returncode != 0:
                return CapabilityResult.failed(
                    f"Kunne ikke opprette branch '{branch}': {orphan_proc.stderr.strip()}",
                    capability="pages_publish",
                )
            _git(["rm", "-rf", "--quiet", "."], cwd=tmp_dir)
            for child in Path(tmp_dir).iterdir():
                if child.name == ".git":
                    continue
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()

        branch_root = Path(tmp_dir)
        _write_root_index(branch_root)
        _copy_bundle(export_path, branch_root / "latest")
        run_dir = branch_root / "runs" / run_id
        is_new_run_snapshot = not run_dir.exists()
        _copy_bundle(export_path, run_dir)

        _git(["add", "-A"], cwd=tmp_dir)
        status_proc = _git(["status", "--porcelain"], cwd=tmp_dir)

        latest_url, run_url = (
            _pages_urls(owner_repo[0], owner_repo[1], run_id) if owner_repo else (None, None)
        )
        artifacts = [url for url in (latest_url, run_url) if url]

        if not status_proc.stdout.strip():
            sha = _git(["rev-parse", "HEAD"], cwd=tmp_dir).stdout.strip()
            return CapabilityResult.ok(
                f"Ingen endringer å publisere for kjøring {run_id} — allerede oppdatert.",
                capability="pages_publish",
                evidence=[f"commit_sha={sha}", f"branch={branch}"],
                artifacts=artifacts,
            )

        commit_proc = _git(
            [
                "-c", "user.email=rvv-miniputt-operator@localhost",
                "-c", "user.name=RVV Miniputt operator",
                "commit", "-m", f"Publish run {run_id}",
            ],
            cwd=tmp_dir,
        )
        if commit_proc.returncode != 0:
            return CapabilityResult.failed(
                f"Kunne ikke committe Pages-publisering: {commit_proc.stderr.strip()}",
                capability="pages_publish",
            )
        sha = _git(["rev-parse", "HEAD"], cwd=tmp_dir).stdout.strip()

        if push:
            push_proc = _git(["push", remote, f"{branch}:{branch}"], cwd=repo_root)
            if push_proc.returncode != 0:
                return CapabilityResult.failed(
                    f"Publiserte lokalt (commit {sha}), men push til {remote}/{branch} feilet: "
                    f"{push_proc.stderr.strip()}",
                    capability="pages_publish",
                    evidence=[f"commit_sha={sha}", f"branch={branch}"],
                    problems=[push_proc.stderr.strip()],
                )

        return CapabilityResult.ok(
            f"Publiserte kjøring {run_id} til {branch} (commit {sha[:8]})",
            capability="pages_publish",
            evidence=[
                f"commit_sha={sha}",
                f"branch={branch}",
                f"new_run_snapshot={is_new_run_snapshot}",
            ],
            artifacts=artifacts,
        )
    finally:
        if worktree_added:
            _git(["worktree", "remove", "--force", tmp_dir], cwd=repo_root)
        shutil.rmtree(tmp_dir, ignore_errors=True)
