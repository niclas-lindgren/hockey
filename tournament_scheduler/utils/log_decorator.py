"""
Lightweight call-logging decorator.

Usage::

    from tournament_scheduler.utils.log_decorator import log_call

    @log_call
    def scrape_source(url: str, cache: bool = True) -> list[dict]:
        ...

Produces::

    [pipeline.stage2_scraping] INFO  CALL scrape_source('https://...', cache=True)
    [pipeline.stage2_scraping] INFO  RETURN scrape_source -> [{'date': ...}, ...]  (42 events)

Every ``@log_call``-decorated function logs its **qualified name** (including the
class for methods), all positional and keyword arguments, and the return value
(truncated at 300 characters if longer).  Exceptions are logged with the error
message and re-raised.

The logger name is taken from ``func.__module__`` so entries appear under the
module that **owns** the function, not this decorator module.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

# Characters beyond this are replaced with "…" in return-value output.
_MAX_RESULT_LEN = 300


def log_call(func: F) -> F:
    """Decorate *func* so every call is logged with params and return value."""

    logger = logging.getLogger(func.__module__)

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Build a human-readable parameter string
        parts: list[str] = []
        if args:
            parts.append(", ".join(_safe_repr(a) for a in args))
        if kwargs:
            parts.append(", ".join(f"{k}={_safe_repr(v)}" for k, v in kwargs.items()))
        sig = ", ".join(parts)

        qualname = _qualname(func)
        logger.info("CALL %s(%s)", qualname, sig)

        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            logger.error("ERROR %s → %s: %s", qualname, type(exc).__name__, exc)
            raise

        # Log return value, truncated if needed
        result_repr = _safe_repr(result)
        if len(result_repr) > _MAX_RESULT_LEN:
            suffix = "…"
            result_repr = result_repr[: _MAX_RESULT_LEN] + suffix
        logger.info("RETURN %s → %s", qualname, result_repr)

        return result

    return wrapper  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _qualname(func: Callable[..., Any]) -> str:
    """Return ``module.qualname`` when available, otherwise ``func.__name__``."""
    mod = getattr(func, "__module__", None)
    qn = getattr(func, "__qualname__", None) or func.__name__
    if mod:
        return f"{mod}.{qn}"
    return qn


def _safe_repr(obj: Any, max_len: int = 200) -> str:
    """repr() that limits individual argument values to *max_len* chars."""
    s = repr(obj)
    if len(s) > max_len:
        s = s[:max_len] + "…"
    return s
