"""Pipeline state manager — JSON checkpoint files per pipeline stage.

Each stage writes its output to a dedicated JSON checkpoint file inside a
configurable work directory (default ``.pipeline/`` relative to the current
working directory).  A ``status`` field tracks whether a stage is ``pending``,
``done``, or ``failed``, enabling a ``--resume-from`` flag to skip completed
stages.

Stage checkpoint file names:

=============  ==========================
Stage          File
=============  ==========================
1 (config)     ``stage1_config.json``
2 (scraping)   ``stage2_scraping.json``
3 (planning)   ``stage3_planning.json``
4 (export)     ``stage4_export.json``
=============  ==========================

Typical usage::

    state = PipelineState(work_dir=".pipeline")

    # Write stage output
    state.write_stage(StageName.CONFIG, {"teams": [...], "date_range": ...})

    # Mark as done
    state.mark_done(StageName.CONFIG)

    # Read in the next stage
    cfg = state.read_stage(StageName.CONFIG)

    # Check whether a stage can be skipped
    if state.is_done(StageName.CONFIG):
        ...

    # Resume from a given stage (skip all earlier done stages)
    from_stage = state.resolve_resume_from("scraping")
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_WORK_DIR = ".pipeline"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StageStatus(str, Enum):
    """Status values for a pipeline stage checkpoint."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class StageName(str, Enum):
    """Canonical names for the four pipeline stages."""

    CONFIG = "config"
    SCRAPING = "scraping"
    PLANNING = "planning"
    EXPORT = "export"

    @property
    def index(self) -> int:
        """1-based index matching the stage number used in file names."""
        return _STAGE_ORDER.index(self) + 1

    @property
    def filename(self) -> str:
        """JSON checkpoint file name for this stage."""
        return f"stage{self.index}_{self.value}.json"


# Ordered list used by StageName.index
_STAGE_ORDER: list[StageName] = [
    StageName.CONFIG,
    StageName.SCRAPING,
    StageName.PLANNING,
    StageName.EXPORT,
]

# Accepts human-friendly aliases for --resume-from
_ALIASES: dict[str, StageName] = {
    "1": StageName.CONFIG,
    "config": StageName.CONFIG,
    "stage1": StageName.CONFIG,
    "2": StageName.SCRAPING,
    "scraping": StageName.SCRAPING,
    "stage2": StageName.SCRAPING,
    "3": StageName.PLANNING,
    "planning": StageName.PLANNING,
    "plan": StageName.PLANNING,
    "stage3": StageName.PLANNING,
    "4": StageName.EXPORT,
    "export": StageName.EXPORT,
    "stage4": StageName.EXPORT,
}


# ---------------------------------------------------------------------------
# PipelineState
# ---------------------------------------------------------------------------


class PipelineState:
    """Read/write JSON checkpoint files for the four pipeline stages.

    Parameters
    ----------
    work_dir:
        Directory where checkpoint files are stored.  Created automatically
        if it does not exist.
    """

    def __init__(self, work_dir: str | os.PathLike[str] = _DEFAULT_WORK_DIR) -> None:
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def checkpoint_path(self, stage: StageName) -> Path:
        """Return the absolute path to a stage checkpoint file."""
        return self.work_dir / stage.filename

    # ------------------------------------------------------------------
    # Read / write
    # ------------------------------------------------------------------

    def write_stage(
        self,
        stage: StageName,
        data: dict[str, Any],
        *,
        status: StageStatus = StageStatus.RUNNING,
    ) -> Path:
        """Write (or overwrite) the checkpoint file for *stage*.

        The checkpoint envelope wraps *data* in a top-level object that also
        contains ``status``, ``stage``, and ``updated_at`` fields so any tool
        inspecting the file can understand its state without knowing the schema
        of *data*.

        Returns the path written.
        """
        envelope: dict[str, Any] = {
            "stage": stage.value,
            "status": status.value,
            "updated_at": datetime.now(tz=timezone.utc).isoformat(),
            "data": data,
        }
        path = self.checkpoint_path(stage)
        path.write_text(json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8")
        if status in (StageStatus.DONE, StageStatus.FAILED):
            self._invalidate_downstream(stage, reason=self._default_stale_reason(stage, status))
        return path

    def mark_done(self, stage: StageName) -> None:
        """Update the status field of an existing checkpoint to ``done``.

        If no checkpoint exists yet a minimal one is created.
        """
        self._set_status(stage, StageStatus.DONE)

    def mark_failed(self, stage: StageName, error: str = "") -> None:
        """Update the status field of an existing checkpoint to ``failed``.

        Optionally records an *error* string in the checkpoint.
        """
        self._set_status(stage, StageStatus.FAILED, extra={"error": error} if error else {})

    def read_stage(self, stage: StageName) -> dict[str, Any]:
        """Read the *data* payload of a checkpoint file.

        Returns an empty dict if no checkpoint exists yet.
        """
        path = self.checkpoint_path(stage)
        if not path.exists():
            return {}
        envelope = json.loads(path.read_text(encoding="utf-8"))
        return envelope.get("data", {})

    def read_envelope(self, stage: StageName) -> dict[str, Any]:
        """Read the full checkpoint envelope (including ``status``, etc.)."""
        path = self.checkpoint_path(stage)
        if not path.exists():
            return {"stage": stage.value, "status": StageStatus.PENDING.value, "data": {}}
        return json.loads(path.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def status(self, stage: StageName) -> StageStatus:
        """Return the current status of *stage* without loading the full envelope."""
        envelope = self.read_envelope(stage)
        try:
            return StageStatus(envelope.get("status", StageStatus.PENDING.value))
        except ValueError:
            return StageStatus.PENDING

    def is_done(self, stage: StageName) -> bool:
        """Return ``True`` if *stage* has status ``done``."""
        return self.status(stage) == StageStatus.DONE

    def is_failed(self, stage: StageName) -> bool:
        """Return ``True`` if *stage* has status ``failed``."""
        return self.status(stage) == StageStatus.FAILED

    def is_stale(self, stage: StageName) -> bool:
        """Return ``True`` if *stage* was invalidated by an upstream stage."""
        return bool(self.read_envelope(stage).get("stale", False))

    def summary(self) -> dict[StageName, StageStatus]:
        """Return a mapping of every stage to its current status."""
        return {stage: self.status(stage) for stage in _STAGE_ORDER}

    # ------------------------------------------------------------------
    # Resume helpers
    # ------------------------------------------------------------------

    def resolve_resume_from(self, value: str) -> StageName:
        """Parse a ``--resume-from`` CLI value into a :class:`StageName`.

        Accepts stage names (``config``, ``scraping``, ``planning``,
        ``export``), their aliases (``plan``, ``stage2``, …), and 1-based
        integers (``"1"`` – ``"4"``).

        Raises
        ------
        ValueError
            If *value* is not a recognised stage name or alias.
        """
        key = value.strip().lower()
        stage = _ALIASES.get(key)
        if stage is None:
            valid = sorted(set(_ALIASES.keys()))
            raise ValueError(
                f"Unknown stage {value!r}. Valid values: {', '.join(valid)}"
            )
        return stage

    def stages_to_run(self, resume_from: StageName | None = None) -> list[StageName]:
        """Return the ordered list of stages that should be executed.

        If *resume_from* is given, stages *before* it that are already
        ``done`` are skipped.  If a previous stage is *not* done but
        *resume_from* would skip it, a :class:`ValueError` is raised to
        prevent running with missing upstream data.

        Parameters
        ----------
        resume_from:
            If ``None``, all four stages are returned (normal full run).
        """
        if resume_from is None:
            return list(_STAGE_ORDER)

        resume_idx = _STAGE_ORDER.index(resume_from)

        # Verify all earlier stages are done
        for stage in _STAGE_ORDER[:resume_idx]:
            if not self.is_done(stage):
                raise ValueError(
                    f"Cannot resume from '{resume_from.value}': "
                    f"stage '{stage.value}' is not done yet "
                    f"(status: {self.status(stage).value})"
                )

        return _STAGE_ORDER[resume_idx:]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def write_judgment(
        self,
        stage: StageName,
        verdict: str,
        reasoning: str = "",
        backend: str = "",
    ) -> None:
        """Persist a headless judge verdict into the stage checkpoint envelope.

        The judgment is stored under a top-level ``judgment`` key so it is
        visible when inspecting ``.pipeline/stage*.json`` files.  The stage's
        ``status`` and ``data`` fields are not modified.

        Args:
            stage:     The stage this judgment belongs to.
            verdict:   ``"PROCEED"`` or ``"ABORT"`` (or the full first line of
                       the judge's response).
            reasoning: Optional explanation from the judge (remainder of the
                       response after the verdict keyword).
            backend:   The backend identifier used (e.g. ``"llm_bridge"``).
        """
        envelope = self.read_envelope(stage)
        envelope["judgment"] = {
            "verdict": verdict,
            "reasoning": reasoning,
            "backend": backend,
            "judged_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        envelope["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
        path = self.checkpoint_path(stage)
        path.write_text(json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8")

    def write_approval(
        self,
        stage: "StageName",
        decision: str,
        rationale: str = "",
        blockers: "list[str] | None" = None,
        proposed_changes: "list[str] | None" = None,
    ) -> None:
        """Persist an LLM approval gate verdict into the stage checkpoint envelope.

        The verdict is stored under a top-level ``llm_approval`` key so it is
        visible when inspecting ``.pipeline/stage*.json`` files.  The stage's
        ``status`` and ``data`` fields are not modified.

        Args:
            stage:            The stage this approval verdict belongs to.
            decision:         ``"GO"`` or ``"NO_GO"``.
            rationale:        Short explanation from the LLM.
            blockers:         List of blocker strings (if any) from the LLM.
            proposed_changes: List of suggested change strings (if any) from the LLM.
        """
        envelope = self.read_envelope(stage)
        envelope["llm_approval"] = {
            "decision": decision,
            "rationale": rationale,
            "blockers": blockers or [],
            "proposed_changes": proposed_changes or [],
            "decided_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        envelope["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
        path = self.checkpoint_path(stage)
        path.write_text(json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8")

    def _set_status(
        self,
        stage: StageName,
        status: StageStatus,
        extra: dict[str, Any] | None = None,
    ) -> None:
        envelope = self.read_envelope(stage)
        envelope["status"] = status.value
        envelope["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
        if extra:
            envelope.update(extra)
        path = self.checkpoint_path(stage)
        path.write_text(json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8")
        if status in (StageStatus.DONE, StageStatus.FAILED):
            reason = None
            if extra:
                reason = extra.get("error")
            self._invalidate_downstream(stage, reason=reason or self._default_stale_reason(stage, status))

    def _default_stale_reason(self, stage: StageName, status: StageStatus) -> str:
        if status == StageStatus.FAILED:
            return f"Upstream stage {stage.value} failed"
        return f"Upstream stage {stage.value} changed"

    def _downstream_stages(self, stage: StageName) -> list[StageName]:
        idx = _STAGE_ORDER.index(stage)
        return _STAGE_ORDER[idx + 1 :]

    def _invalidate_downstream(self, stage: StageName, *, reason: str) -> None:
        for downstream in self._downstream_stages(stage):
            path = self.checkpoint_path(downstream)
            if not path.exists():
                continue
            envelope = self.read_envelope(downstream)
            envelope["status"] = StageStatus.FAILED.value
            envelope["stale"] = True
            envelope["stale_from"] = stage.value
            envelope["stale_reason"] = reason
            envelope["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
            if not envelope.get("error"):
                envelope["error"] = f"Stale etter endring i {stage.value}: {reason}"
            path.write_text(json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8")
