from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_FILE = ROOT / ".agents" / "skills" / "pi-next" / "SKILL.md"


def test_skill_documents_thin_proxy_boundary() -> None:
    text = SKILL_FILE.read_text(encoding="utf-8")

    assert "thin project-local proxy" in text
    assert "shared PS:next workflow" in text
    assert "## Boundary / cleanup target" in text
    assert "Do not duplicate the shared PS:next protocol" in text
    assert "harness-neutral" in text
    assert "pi-next-state.sh" in text


def test_handoff_status_treats_continue_marker_as_blocker() -> None:
    text = (ROOT / ".pi" / "extensions" / "pi-next.ts").read_text(encoding="utf-8")

    assert "continueMarker" in text
    assert "Safe handoff" in text
    assert "Continue marker contents" in text
    assert "!existsSync(cont)" in text
