"""Harness-presence detection for the LLM judge.

When a known harness (Claude Code, Pi, OpenCode, etc.) is orchestrating the
pipeline it will provide its own in-session judgment.  The headless LLM judge
should only be instantiated when *no* harness is active (e.g. cron jobs, CI).

Environment variables checked:
    RVV_HARNESS              — explicit override (any non-empty value → harness active)
    CLAUDE_CODE_SESSION_ID   — set by Claude Code
    PI_SESSION_ID            — set by the Pi harness
    OPENCODE_SESSION_ID      — set by OpenCode
"""

import os

from .interface import LLMJudge

# Env-var indicators that a harness is orchestrating the current run.
_HARNESS_ENV_VARS: tuple[str, ...] = (
    "RVV_HARNESS",
    "CLAUDE_CODE_SESSION_ID",
    "PI_SESSION_ID",
    "OPENCODE_SESSION_ID",
)


def is_harness_active() -> bool:
    """Return True if a known harness session is currently orchestrating the run.

    Checks a fixed set of well-known environment variables.  Any non-empty
    value in any of them is treated as "harness active".

    Returns:
        ``True`` when a harness is detected, ``False`` in headless / cron
        / CI environments.
    """
    return any(os.environ.get(var, "").strip() for var in _HARNESS_ENV_VARS)


def get_judge_if_headless(backend: str | None = None) -> "LLMJudge | None":
    """Return an LLMJudge instance only when no harness is active.

    Convenience helper for pipeline stages — callers do not need to duplicate
    the harness-detection logic:

    .. code-block:: python

        judge = get_judge_if_headless()
        if judge is not None:
            verdict = judge.judge(prompt)
        # else: harness is present and will evaluate interactively

    Args:
        backend: Passed through to :func:`~tournament_scheduler.llm_judge.create_judge`.
                 Defaults to the ``RVV_JUDGE_BACKEND`` env var.

    Returns:
        A :class:`~tournament_scheduler.llm_judge.LLMJudge` instance, or
        ``None`` if a harness is detected.
    """
    if is_harness_active():
        return None

    # Import here to avoid a circular import at module level.
    from . import create_judge  # noqa: PLC0415

    return create_judge(backend)
