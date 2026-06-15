"""Recovery hints and blocked-source warnings for Stage 2 scraping."""

from __future__ import annotations

import os
from typing import Any

from .scraper_strategies import get_strategy, requires_credentials
from .state import PipelineState, StageName


def _recovery_hint_for_source(source_name: str) -> str:
    """Return a Norwegian hint that explains how to recover from a blocked source."""
    try:
        strategy = get_strategy(source_name)
        if strategy and requires_credentials(strategy):
            engine = strategy.engine.value.replace("_", " ")
            vars_list = ", ".join(strategy.credential_env_vars)
            missing = [var for var in strategy.credential_env_vars if not os.environ.get(var)]
            if missing:
                credential_text = f"Mangler miljovariablene {', '.join(missing)}."
            else:
                credential_text = f"Fyll innloggingsdetaljene for {engine}."
            return (
                f"{credential_text} Kildens innlogging bruker {vars_list}. Kjor `rvv-miniputt run` pa nytt nar kilden er tilgjengelig, "
                "eller bruk `rvv-miniputt run --allow-missing-sources` for a fortsette med delvise resultater."
            )
    except Exception:
        pass
    return (
        "Kjor `rvv-miniputt run` pa nytt nar kalenderen er tilgjengelig, "
        "eller bruk `rvv-miniputt run --allow-missing-sources` for a fortsette med delvise resultater."
    )


def _blocked_sources_warning(
    blocked: list[dict[str, Any]],
    state: PipelineState,
    *,
    allow_missing_sources: bool,
) -> str:
    names = ", ".join(sorted({b.get('name', '?') for b in blocked})) or "ukjent kilde"
    path = state.checkpoint_path(StageName.SCRAPING)
    recovery = _recovery_hint_for_source(blocked[0].get("name", "")) if blocked else _recovery_hint_for_source("")
    prefix = "Delvise resultater er lagret" if allow_missing_sources else "Delvise resultater er lagret, men Stage 2 er markert som feilet"
    return f"{prefix} i {path}. Blokkerte kilder: {names}. {recovery}"
