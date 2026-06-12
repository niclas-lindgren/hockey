from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKLOG_SCRIPT = ROOT / ".agents" / "skills" / "pi-next" / "scripts" / "pi-next-backlog.sh"
STATE_SCRIPT = ROOT / ".agents" / "skills" / "pi-next" / "scripts" / "pi-next-state.sh"


def write_project(tmp_path: Path, backlog: str, plan: str | None = None) -> Path:
    project = tmp_path / "project"
    ps_dir = project / ".ps-next"
    ps_dir.mkdir(parents=True)
    (ps_dir / "PROJECT.md").write_text("# Test\n")
    (ps_dir / "BACKLOG.md").write_text(backlog)
    if plan is not None:
        (ps_dir / "PLAN.md").write_text(plan)
    return project


def run_script(script: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(script), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def test_done_moves_multiline_item_from_open_to_done_preserving_continuation(tmp_path: Path) -> None:
    project = write_project(
        tmp_path,
        """# Backlog

## Open

- [1] [ ] First open item
  continuation line one
  continuation line two
- [2] [ ] Second open item

## Done
- [3] [x] Older done item (2026-01-01)
""",
    )

    result = run_script(BACKLOG_SCRIPT, str(project), "done", "1")

    assert result.stdout.strip() == "Marked [1] done."
    updated = (project / ".ps-next" / "BACKLOG.md").read_text()
    open_section = updated.split("## Open", 1)[1].split("## Done", 1)[0]
    done_section = updated.split("## Done", 1)[1]
    assert "- [1] [ ]" not in open_section
    assert "- [2] [ ] Second open item" in open_section
    assert "- [1] [x] First open item" in done_section
    assert "  continuation line one" in done_section
    assert "  continuation line two" in done_section


def test_list_and_state_count_only_unchecked_items_in_open_section(tmp_path: Path) -> None:
    project = write_project(
        tmp_path,
        """# Backlog

## Open

- [10] [ ] Real open
- [11] [x] Checked but still in open during cleanup window

## Done
- [12] [ ] Malformed old item should not count because it is under done
""",
        plan="""# Plan: Test
**Goal:** done

## Tasks
- [ ] Do work
  - Files: x
  - Approach: y
- [x] Done work
  - Files: x
  - Approach: y

## Acceptance Criteria
- [ ] run: true

## Log
""",
    )

    listed = run_script(BACKLOG_SCRIPT, str(project), "list").stdout.strip().splitlines()
    state = run_script(STATE_SCRIPT, str(project)).stdout

    assert listed == ["- [10] [ ] Real open"]
    assert "OPEN_BACKLOG=1" in state
    assert "BACKLOG_TOP_ID=10" in state
    assert "UNCHECKED=1" in state
    assert "CHECKED=1" in state


def test_add_rejects_existing_duplicate_ids(tmp_path: Path) -> None:
    project = write_project(
        tmp_path,
        """# Backlog

## Open
- [5] [ ] Duplicate A

## Done
- [5] [x] Duplicate B (2026-01-01)
""",
    )

    result = run_script(BACKLOG_SCRIPT, str(project), "add", "New item", check=False)

    assert result.returncode != 0
    assert "Duplicate backlog IDs found: 5" in result.stderr


def test_done_rejects_duplicate_target_id(tmp_path: Path) -> None:
    project = write_project(
        tmp_path,
        """# Backlog

## Open
- [5] [ ] Duplicate A

## Done
- [5] [x] Duplicate B (2026-01-01)
""",
    )

    result = run_script(BACKLOG_SCRIPT, str(project), "done", "5", check=False)

    assert result.returncode != 0
    assert "duplicate/conflicting IDs" in result.stderr
