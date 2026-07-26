"""Static validation of the Electron packaging/release configuration.

Deliberately does not invoke electron-builder or produce a real build
artifact (no Electron download, no code signing) — this is the fast,
required-CI-tier check; a real packaged build is exercised by the separate
desktop-build.yml / release.yml workflows. This is also a regression guard
for a real bug found in issue #7: electron-builder's GitHub publish target
pointed at the wrong repository owner.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_JSON = ROOT / "apps" / "desktop" / "package.json"

# The actual GitHub repo this project is hosted in. Keep in sync with the
# "Repository Scope" the harness reports, and with .github/workflows/release.yml.
EXPECTED_OWNER = "niclas-lindgren"
EXPECTED_REPO = "hockey"


def _load_package_json() -> dict:
    return json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))


class TestPackageJsonStructure:
    def test_is_valid_json(self):
        _load_package_json()  # raises if invalid

    def test_has_required_top_level_fields(self):
        data = _load_package_json()
        for field in ("name", "version", "main", "build"):
            assert field in data, f"apps/desktop/package.json missing {field!r}"

    def test_main_entry_point_exists(self):
        data = _load_package_json()
        assert (ROOT / "apps" / "desktop" / data["main"]).exists()


class TestElectronBuilderConfig:
    def test_app_id_and_product_name_present(self):
        build = _load_package_json()["build"]
        assert build.get("appId")
        assert build.get("productName")

    def test_publish_target_matches_actual_repo(self):
        """Regression guard: electron-builder's GitHub publish config
        previously pointed at owner "niclasl" instead of this repo's real
        owner "niclas-lindgren" — a build with --publish would have tried
        to publish to the wrong (likely inaccessible) repository."""
        publish = _load_package_json()["build"].get("publish")
        assert publish is not None, "build.publish is not configured"
        assert publish["provider"] == "github"
        assert publish["owner"] == EXPECTED_OWNER
        assert publish["repo"] == EXPECTED_REPO

    def test_extra_resources_points_at_backend_output_dir(self):
        """The backend PyInstaller output path must match what
        scripts/package-desktop-backend.sh and the CI workflows actually
        produce (dist/desktop-backend/), or a packaged app silently ships
        without its Python backend."""
        build = _load_package_json()["build"]
        extra_resources = build.get("extraResources") or []
        backend_entries = [e for e in extra_resources if "backend" in str(e.get("to", ""))]
        assert backend_entries, "no extraResources entry maps to a backend/ directory"
        assert any("dist/desktop-backend" in e.get("from", "") for e in backend_entries)

    def test_targets_configured_for_all_three_platforms(self):
        build = _load_package_json()["build"]
        for platform in ("mac", "win", "linux"):
            assert platform in build, f"build.{platform} target is not configured"
            assert build[platform].get("target"), f"build.{platform}.target is empty"


class TestPyInstallerEntryPointExists:
    def test_desktop_server_module_is_importable(self):
        # Import-only check: catches syntax errors / broken imports in the
        # exact module PyInstaller bundles (tournament_scheduler/desktop_server.py)
        # without needing PyInstaller itself installed.
        import tournament_scheduler.desktop_server  # noqa: F401

    def test_desktop_server_has_a_main_entry_point(self):
        import tournament_scheduler.desktop_server as desktop_server_module

        assert callable(desktop_server_module.main)


class TestReleaseWorkflowConfig:
    """Cross-check the release workflow installs what desktop_server.py
    actually needs at runtime, on every platform it builds for."""

    RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"

    def test_release_workflow_exists(self):
        assert self.RELEASE_WORKFLOW.exists()

    def test_keyring_is_installed_unconditionally(self):
        """Regression guard: keyring was previously only pip-installed for
        the macOS/Windows build legs, even though desktop_server.py imports
        it at runtime on every platform and the Linux leg bundles
        keyring.backends.SecretService as a PyInstaller hidden import."""
        text = self.RELEASE_WORKFLOW.read_text(encoding="utf-8")
        install_section = text.split("Build Python backend")[0]
        assert "pip install keyring" in install_section
        # Must not be conditioned on a specific matrix.os anymore.
        keyring_line = next(
            line for line in install_section.splitlines() if "pip install keyring" in line
        )
        assert "matrix.os" not in keyring_line
