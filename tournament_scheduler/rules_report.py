"""Rules-report helper for `SeasonPlanner`."""

from __future__ import annotations

from typing import Dict, List


def rules_report(planner) -> List[Dict[str, str]]:
    """Delegate to the planner's preserved rules-report implementation."""
    return planner._rules_report_impl()
