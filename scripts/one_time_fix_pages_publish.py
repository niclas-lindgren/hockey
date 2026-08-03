#!/usr/bin/env python3
"""One-time repair for preserving independently published Pages assets."""

from __future__ import annotations

import re
from pathlib import Path
from textwrap import dedent

SOURCE = Path("tournament_scheduler/pipeline/pages_publish.py")
TEST = Path("tests/test_pages_publish_preservation.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old in text:
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise SystemExit(f"Could not patch {label}")


def patch_source() -> None:
    text = SOURCE.read_text(encoding="utf-8")

    if "_PRESERVED_LATEST_PATHS" not in text:
        text = replace_once(
            text,
            "_GIT_TIMEOUT_SECONDS = 120\n",
            dedent(
                '''\
                _GIT_TIMEOUT_SECONDS = 120

                # These assets are published independently from the season-plan bundle.
                # A season-plan publish must never delete them from /latest/.
                _PRESERVED_LATEST_PATHS = ("activities", "activities.json", "registered-teams")
                '''
            ),
            "preserved path constants",
        )

    if "def _copy_path(" not in text:
        pattern = re.compile(
            r"def _copy_bundle\(export_dir: Path, dest_dir: Path\) -> None:\n.*?\n\ndef _write_root_index",
            re.DOTALL,
        )
        replacement = dedent(
            '''\
            def _copy_path(source: Path, destination: Path) -> None:
                """Copy one file or directory, creating its destination parent."""
                destination.parent.mkdir(parents=True, exist_ok=True)
                if source.is_dir():
                    shutil.copytree(source, destination)
                else:
                    shutil.copyfile(source, destination)


            def _copy_bundle(
                export_dir: Path,
                dest_dir: Path,
                *,
                preserve_existing: tuple[str, ...] = (),
            ) -> None:
                """Replace *dest_dir* with *export_dir*, preserving independent assets.

                Entries named by *preserve_existing* survive when they already exist in
                *dest_dir* and the new bundle does not contain a replacement. This keeps
                independently published activity and registration pages available when a
                season-plan bundle is published.

                Adds an ``index.html`` when the bundle doesn't already have one (falling
                back to a copy of ``season_plan.html``) so the directory resolves on its
                own as a Pages URL.
                """
                preserved_root = Path(tempfile.mkdtemp(prefix="rvv-pages-preserved-"))
                try:
                    if dest_dir.exists():
                        for relative_name in preserve_existing:
                            source = dest_dir / relative_name
                            if not source.exists() or (export_dir / relative_name).exists():
                                continue
                            _copy_path(source, preserved_root / relative_name)
                        shutil.rmtree(dest_dir)

                    shutil.copytree(export_dir, dest_dir)

                    for relative_name in preserve_existing:
                        source = preserved_root / relative_name
                        if source.exists():
                            _copy_path(source, dest_dir / relative_name)
                finally:
                    shutil.rmtree(preserved_root, ignore_errors=True)

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


            def _write_root_index'''
        )
        text, count = pattern.subn(replacement, text, count=1)
        if count != 1:
            raise SystemExit("Could not replace _copy_bundle")

    old_remove = "    remove = sorted(existing - bundle_rels)\n"
    new_remove = (
        "    preserved_roots = tuple(\n"
        "        root\n"
        "        for root in _PRESERVED_LATEST_PATHS\n"
        "        if not any(name == root or name.startswith(f\"{root}/\") for name in bundle_contents)\n"
        "    )\n"
        "    remove = sorted(\n"
        "        path\n"
        "        for path in existing - bundle_rels\n"
        "        if not any(\n"
        "            path == f\"latest/{root}\" or path.startswith(f\"latest/{root}/\")\n"
        "            for root in preserved_roots\n"
        "        )\n"
        "    )\n"
    )
    text = replace_once(text, old_remove, new_remove, "diff_latest removal handling")

    text = replace_once(
        text,
        '        _copy_bundle(export_path, branch_root / "latest")\n',
        '        _copy_bundle(\n'
        '            export_path,\n'
        '            branch_root / "latest",\n'
        '            preserve_existing=_PRESERVED_LATEST_PATHS,\n'
        '        )\n',
        "latest publish call",
    )

    text = replace_once(
        text,
        "        _copy_bundle(export_path, run_dir)\n",
        '        _copy_bundle(branch_root / "latest", run_dir)\n',
        "run snapshot call",
    )

    old_rollback = (
        '        latest_dir = Path(tmp_dir) / "latest"\n'
        "        if latest_dir.exists():\n"
        "            shutil.rmtree(latest_dir)\n"
        "        shutil.copytree(run_dir, latest_dir)\n"
    )
    new_rollback = (
        '        latest_dir = Path(tmp_dir) / "latest"\n'
        "        _copy_bundle(\n"
        "            run_dir,\n"
        "            latest_dir,\n"
        "            preserve_existing=_PRESERVED_LATEST_PATHS,\n"
        "        )\n"
    )
    text = replace_once(text, old_rollback, new_rollback, "rollback preservation")

    SOURCE.write_text(text, encoding="utf-8")


def write_tests() -> None:
    TEST.write_text(
        dedent(
            '''\
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
                (local / "README.md").write_text("hello\\n", encoding="utf-8")
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
            '''
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    patch_source()
    write_tests()
    print("Patched Pages publisher and wrote regression tests.")
