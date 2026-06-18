"""CLI command for inspecting Stage 2 blocked and zero-event sources."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _cmd_recovery_targets(args: argparse.Namespace) -> int:
    """Handle ``rvv-miniputt recovery-targets``.

    Reads the Stage 2 scraping checkpoint and prints a JSON array of sources
    that are either blocked or returned zero events.  Each entry has the shape::

        {"name": "Sandefjord", "url": "https://...", "reason": "blocked|zero_events",
         "block_reason": "..." | null, "llm_fallback": true|false}

    This output is intended for consumption by the harness agent when deciding
    whether to trigger LLM-assisted scraping for specific sources.
    """
    work_dir = Path(args.work_dir)
    checkpoint_path = work_dir / "stage2_scraping.json"

    if not checkpoint_path.exists():
        print(
            json.dumps({"error": f"Stage 2 checkpoint not found: {checkpoint_path}"}),
            file=sys.stderr,
        )
        return 1

    with checkpoint_path.open() as f:
        raw = json.load(f)

    # Checkpoint may wrap data under a "data" key (PipelineState format)
    data = raw.get("data", raw)
    sources: list[dict] = data.get("sources", [])

    targets = []
    for source in sources:
        name = source.get("name", "")
        url = source.get("url", "")
        blocked = source.get("blocked", False)
        event_count = source.get("event_count", 0)
        block_reason = source.get("block_reason") or None
        llm_fallback = source.get("llm_fallback", False)
        skipped = source.get("skipped", False)

        if skipped:
            continue

        if blocked:
            targets.append({
                "name": name,
                "url": url,
                "reason": "blocked",
                "block_reason": block_reason,
                "llm_fallback": llm_fallback,
            })
        elif event_count == 0:
            targets.append({
                "name": name,
                "url": url,
                "reason": "zero_events",
                "block_reason": None,
                "llm_fallback": llm_fallback,
            })

    print(json.dumps(targets, ensure_ascii=False, indent=2))
    return 0
