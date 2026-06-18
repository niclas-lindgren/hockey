"""Plan critic: analyse a Stage 3 SeasonPlan and return ranked issue strings.

This module is intentionally free of LLM calls and external dependencies.
It reads the SeasonPlan data model and returns up to 5 actionable issue strings
ranked by severity (most severe first).
"""
from __future__ import annotations

import calendar
from collections import defaultdict
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from tournament_scheduler.models import SeasonPlan


def generate_critic_summary(plan: "SeasonPlan") -> List[str]:
    """Analyse *plan* and return up to 5 ranked issue strings with fix proposals.

    Severity ranking (highest first):
    1. Fairness gate "fail" metrics
    2. Arena-day collisions
    3. Game count outliers (spread > 4)
    4. Fairness gate "warn" metrics
    5. Hosting clumps (>2 tournaments per club per month)
    6. Low month balance (score < 0.6)

    Returns an empty list if no issues are detected.
    """
    fail_issues: List[str] = []
    collision_issues: List[str] = []
    outlier_issues: List[str] = []
    warn_issues: List[str] = []
    clump_issues: List[str] = []
    balance_issues: List[str] = []

    # ------------------------------------------------------------------
    # 1. Fairness gate (fail metrics)
    # ------------------------------------------------------------------
    fairness_gate = getattr(plan, "fairness_gate", {}) or {}
    gate_status = fairness_gate.get("status", "pass")
    if gate_status in ("warn", "fail"):
        for metric in fairness_gate.get("metrics", []):
            m_status = metric.get("status", "pass")
            label = metric.get("label", "unknown metric")
            value = metric.get("value")
            threshold = metric.get("threshold")
            detail = metric.get("detail", "")
            if m_status == "fail":
                msg = f"Fairness gate FAIL: {label} (value={value}, threshold={threshold})"
                if detail:
                    msg = f"Fairness gate FAIL: {label} — {detail}"
                fail_issues.append(msg[:120])
            elif m_status == "warn":
                msg = f"Fairness gate warning: {label} (value={value}, threshold={threshold})"
                if detail:
                    msg = f"Fairness gate warning: {label} — {detail}"
                warn_issues.append(msg[:120])

    # ------------------------------------------------------------------
    # 2. Arena-day collisions
    # ------------------------------------------------------------------
    collisions = getattr(plan, "arena_day_collisions", []) or []
    if collisions:
        collision_issues.append(
            f"{len(collisions)} arena-day collision(s) detected — "
            "review date assignments for arenas scheduled on the same day"
        )

    # ------------------------------------------------------------------
    # 3. Game count outliers
    # ------------------------------------------------------------------
    team_game_counts: dict = getattr(plan, "team_game_counts", {}) or {}
    game_count_spread: int = getattr(plan, "game_count_spread", 0) or 0
    if game_count_spread > 4 and team_game_counts:
        max_team = max(team_game_counts, key=team_game_counts.__getitem__)
        min_team = min(team_game_counts, key=team_game_counts.__getitem__)
        max_val = team_game_counts[max_team]
        min_val = team_game_counts[min_team]
        outlier_issues.append(
            f"Game count spread {game_count_spread}: {max_team} plays {max_val} games "
            f"vs {min_team}'s {min_val} — redistribute game assignments"
        )

    # ------------------------------------------------------------------
    # 5. Hosting clumps: >2 tournaments at same club in same month
    # ------------------------------------------------------------------
    tournaments = getattr(plan, "tournaments", []) or []
    host_month_counts: dict = defaultdict(int)
    for t in tournaments:
        if getattr(t, "cancelled", False):
            continue
        host_club = getattr(t, "host_club", None)
        t_date = getattr(t, "date", None)
        if host_club and t_date:
            host_month_counts[(host_club, t_date.year, t_date.month)] += 1

    for (club, year, month), count in sorted(host_month_counts.items()):
        if count > 2:
            month_name = calendar.month_name[month]
            clump_issues.append(
                f"{club} hosts {count} tournaments in {month_name} {year} — "
                "consider moving one to another club"
            )

    # ------------------------------------------------------------------
    # 6. Low month balance
    # ------------------------------------------------------------------
    month_balance_score: float = getattr(plan, "month_balance_score", 1.0) or 1.0
    if month_balance_score < 0.6:
        balance_issues.append(
            f"Tournaments are unevenly spread across months "
            f"(balance score={month_balance_score:.2f}) — consider redistributing"
        )

    # ------------------------------------------------------------------
    # Combine by severity rank and cap at 5
    # ------------------------------------------------------------------
    all_issues = (
        fail_issues
        + collision_issues
        + outlier_issues
        + warn_issues
        + clump_issues
        + balance_issues
    )
    return all_issues[:5]


if __name__ == "__main__":
    pass
