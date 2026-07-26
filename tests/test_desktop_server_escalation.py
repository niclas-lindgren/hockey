"""Tests for the desktop backend's operator/escalation endpoints and for the
removal of the dead, broken ``/run`` route (issue #7: the desktop app should
consume the same run manifest / escalation state as the CLI, not duplicate
its own scheduling or recovery behavior).
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from tournament_scheduler.pipeline.escalation import Question, raise_question
from tournament_scheduler.pipeline.run_manifest import RunManifest


@pytest.fixture
def desktop_server(tmp_path, monkeypatch):
    """Start the real desktop HTTP backend on an ephemeral port, isolated to tmp_path."""
    import tournament_scheduler.desktop_server as desktop_server_module

    app_dir = tmp_path / "app-dir"
    app_dir.mkdir()
    monkeypatch.setattr(desktop_server_module, "_app_dir", lambda: app_dir)

    work_dir = tmp_path / "pipeline"
    desktop_server_module._write_json(
        desktop_server_module._settings_path(), {"work_dir": str(work_dir)}
    )

    server = ThreadingHTTPServer(("127.0.0.1", 0), desktop_server_module.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        yield base_url, str(work_dir)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _get(url: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _post(url: str, payload: dict) -> tuple[int, dict]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


class TestManifestEndpoint:
    def test_returns_synthesized_manifest_when_no_run_yet(self, desktop_server):
        base_url, _ = desktop_server
        status, data = _get(f"{base_url}/manifest")
        assert status == 200
        assert data["schema_version"] == 1
        assert data["capabilities"] == []

    def test_returns_real_manifest_after_a_run(self, desktop_server):
        base_url, work_dir = desktop_server
        RunManifest(work_dir).start_run("Fyll sesongen for U10")
        status, data = _get(f"{base_url}/manifest")
        assert status == 200
        assert data["objective"] == "Fyll sesongen for U10"


class TestQuestionsEndpoints:
    def test_empty_when_nothing_raised(self, desktop_server):
        base_url, _ = desktop_server
        status, data = _get(f"{base_url}/questions")
        assert status == 200
        assert data["questions"] == []

    def test_lists_unanswered_question(self, desktop_server):
        base_url, work_dir = desktop_server
        RunManifest(work_dir).start_run("objective")
        question = Question(type="credentials", capability="scraping", summary="Kongsberg blocked")
        raise_question(work_dir, question)

        status, data = _get(f"{base_url}/questions")
        assert status == 200
        assert len(data["questions"]) == 1
        assert data["questions"][0]["id"] == question.id

    def test_answer_marks_question_answered_and_removes_it_from_listing(self, desktop_server):
        base_url, work_dir = desktop_server
        RunManifest(work_dir).start_run("objective")
        question = Question(type="credentials", capability="scraping", summary="Kongsberg blocked")
        raise_question(work_dir, question)

        status, data = _post(
            f"{base_url}/questions/answer",
            {"id": question.id, "answer": "set the env var", "decided_by": "niclas"},
        )
        assert status == 200
        assert data["answered"] is True
        assert data["answer"] == "set the env var"

        _, listing = _get(f"{base_url}/questions")
        assert listing["questions"] == []

    def test_answer_unknown_id_returns_404(self, desktop_server):
        base_url, work_dir = desktop_server
        RunManifest(work_dir).start_run("objective")
        status, data = _post(f"{base_url}/questions/answer", {"id": "not-a-real-id", "answer": "x"})
        assert status == 404

    def test_answer_missing_fields_returns_400(self, desktop_server):
        base_url, _ = desktop_server
        status, _data = _post(f"{base_url}/questions/answer", {"id": "", "answer": ""})
        assert status == 400


class TestDeadRunEndpointRemoved:
    def test_post_run_returns_404(self, desktop_server):
        """POST /run called an undefined _run_pipeline function and was never
        reachable from the actual renderer (which only ever calls
        /run/smart) — removed as dead, broken code."""
        base_url, _ = desktop_server
        status, _data = _post(f"{base_url}/run", {})
        assert status == 404

    def test_run_pipeline_is_not_defined_anywhere(self):
        import tournament_scheduler.desktop_server as desktop_server_module

        assert not hasattr(desktop_server_module, "_run_pipeline")
