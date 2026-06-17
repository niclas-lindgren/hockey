from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_FILE = ROOT / ".agents" / "skills" / "rvv" / "SKILL.md"


def test_rvv_skill_documents_cross_harness_usage_boundary() -> None:
    text = SKILL_FILE.read_text(encoding="utf-8")

    assert "Non-Pi / cross-harness usage" in text
    assert "rvv-miniputt" in text
    assert "Pi-only boundary" in text
