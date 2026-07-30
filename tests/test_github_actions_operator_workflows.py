"""Regression tests for browser-based GitHub Actions operator workflows (issue #45)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

WORKFLOW_FILES = {
    "validate": WORKFLOWS / "season-validate.yml",
    "review": WORKFLOWS / "season-review-bundle.yml",
    "publish": WORKFLOWS / "season-publish.yml",
    "rollback": WORKFLOWS / "season-rollback.yml",
}


class Workflow:
    def __init__(self, path: Path):
        self.path = path
        self.text = path.read_text(encoding="utf-8")
        self.data = yaml.safe_load(self.text)

    @property
    def workflow_dispatch(self) -> dict[str, Any]:
        # PyYAML still applies YAML 1.1 booleans, so the GitHub Actions `on`
        # key may parse as True. Support both to keep the test about content,
        # not the parser version.
        on_block = self.data.get("on", self.data.get(True, {}))
        return on_block.get("workflow_dispatch", {})

    @property
    def inputs(self) -> dict[str, Any]:
        return self.workflow_dispatch.get("inputs", {})

    @property
    def jobs(self) -> dict[str, Any]:
        return self.data.get("jobs", {})


WORKFLOWS_PARSED = {name: Workflow(path) for name, path in WORKFLOW_FILES.items()}


def test_all_browser_operator_workflows_exist_and_are_manual():
    for name, workflow in WORKFLOWS_PARSED.items():
        assert workflow.path.exists(), name
        assert workflow.workflow_dispatch, name
        on_block = workflow.data.get("on", workflow.data.get(True, {}))
        assert set(on_block) == {"workflow_dispatch"}
        assert workflow.data.get("concurrency"), name


def test_validation_and_review_generation_never_publish_publicly():
    for name in ["validate", "review"]:
        workflow = WORKFLOWS_PARSED[name]
        assert workflow.data["permissions"]["contents"] == "read"
        assert "scripts/rvv-miniputt operator run" in workflow.text
        assert "--confirm-public" not in workflow.text
        assert "operator publish \\\n            --work-dir \"$WORK_DIR\" \\\n            --dry-run" in workflow.text or name == "validate"
        assert "actions/upload-artifact@v4" in workflow.text
        assert "operator publish --confirm-public" not in workflow.text
        assert "--publish" not in workflow.text


def test_validation_artifact_contains_fingerprint_manifest_logs_and_review_output():
    workflow = WORKFLOWS_PARSED["validate"]

    assert set(workflow.inputs) == {"input_path", "log_level"}
    for expected in [
        "input-fingerprint.json",
        "validation.log",
        "status.json",
        "run_manifest.json",
        "logs/**",
        "export/github-validate",
    ]:
        assert expected in workflow.text
    assert "scripts/check quick" in workflow.text


def test_review_bundle_uploads_review_artifacts_and_privacy_report():
    workflow = WORKFLOWS_PARSED["review"]

    assert workflow.data["permissions"] == {"contents": "read", "issues": "write"}
    for input_name in ["input_path", "iterations", "force_refresh", "log_level", "review_issue_number"]:
        assert input_name in workflow.inputs
    for expected in [
        "input-fingerprint.json",
        "review-run.log",
        "publish-preview.json",
        "review-summary.md",
        "run_manifest.json",
        "public_bundle/pages_privacy_report.json",
        "export/github-review",
        "gh issue comment",
    ]:
        assert expected in workflow.text


def test_publication_is_separate_protected_and_fingerprint_bound():
    workflow = WORKFLOWS_PARSED["publish"]

    assert workflow.data["permissions"] == {"actions": "read", "contents": "write"}
    for input_name in [
        "review_run_id",
        "artifact_name",
        "run_id",
        "export_dir",
        "bundle_fingerprint",
        "confirm_public",
        "no_verify",
    ]:
        assert input_name in workflow.inputs
    assert "environment: pages-publication" in workflow.text
    assert "gh run download" in workflow.text
    assert "EXPECTED_BUNDLE_FINGERPRINT" in workflow.text
    assert "Bundle fingerprint mismatch" in workflow.text
    assert "--dry-run" in workflow.text
    assert "scripts/rvv-miniputt operator publish" in workflow.text
    assert "--confirm-public" in workflow.text
    assert "PUBLISER" in workflow.text
    assert "public_bundle/pages_privacy_report.json" in workflow.text


def test_rollback_is_separate_protected_and_requires_run_id():
    workflow = WORKFLOWS_PARSED["rollback"]

    assert workflow.data["permissions"] == {"contents": "write"}
    assert set(workflow.inputs) == {"run_id", "confirm_rollback", "no_push"}
    assert "environment: pages-publication" in workflow.text
    assert "RULL_TILBAKE" in workflow.text
    assert "scripts/rvv-miniputt operator rollback \"$RUN_ID\"" in workflow.text
    assert "--confirm-public" in workflow.text
    assert "publish-history" in workflow.text
    assert "rollback-result.json" in workflow.text


def test_workflows_delegate_to_canonical_cli_instead_of_reimplementing_policy():
    forbidden_fragments = [
        "python -m tournament_scheduler.pipeline.stage",
        "python -m tournament_scheduler.pipeline.pages_publish",
        "git push origin gh-pages",
        "git checkout gh-pages",
        "git worktree",
        "\n/rvv-miniputt",
        "eval ",
    ]

    for name, workflow in WORKFLOWS_PARSED.items():
        for fragment in forbidden_fragments:
            assert fragment not in workflow.text, f"{name} should not contain {fragment!r}"
        if name in {"validate", "review"}:
            assert "scripts/rvv-miniputt operator run" in workflow.text
        if name == "publish":
            assert "scripts/rvv-miniputt operator publish" in workflow.text
        if name == "rollback":
            assert "scripts/rvv-miniputt operator rollback" in workflow.text
