from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RVV_SKILL_FILE = ROOT / ".agents" / "skills" / "rvv" / "SKILL.md"
RVV_EXTENSION_FILE = ROOT / ".pi" / "extensions" / "rvv-miniputt.ts"
CLAUDE_RUN_FILE = ROOT / ".claude" / "commands" / "rvv-miniputt" / "run.md"


def test_rvv_skill_documents_checkpoint_review_and_single_club_troubleshooting() -> None:
    text = RVV_SKILL_FILE.read_text(encoding="utf-8")

    assert "stage-by-stage pipeline" in text
    assert "review the checkpoint" in text
    assert "rvv_miniputt_scrape" in text
    assert "rvv_miniputt_scrape_llm" in text
    assert "scrape --club" in text
    assert "scrape-llm --club" in text


def test_rvv_extension_exposes_scrape_commands_and_tools() -> None:
    text = RVV_EXTENSION_FILE.read_text(encoding="utf-8")

    assert 'rvv-miniputt scrape' in text
    assert 'rvv-miniputt scrape-llm' in text
    assert 'rvv_miniputt_scrape' in text
    assert 'rvv_miniputt_scrape_llm' in text


def test_claude_run_doc_mentions_single_club_troubleshooting() -> None:
    text = CLAUDE_RUN_FILE.read_text(encoding="utf-8")

    assert "scripts/rvv-miniputt scrape --club <name>" in text
    assert "scripts/rvv-miniputt scrape-llm --club <name>" in text
