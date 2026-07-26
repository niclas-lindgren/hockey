"""Versioned AI-operator run manifest.

The run manifest is the shared data contract that lets an AI operator (or a
human) understand workspace state without parsing console logs: the active
objective, which capability is currently running, input fingerprints, a
timestamped history of capability results, and the final outcome of the run.

It is stored alongside the existing per-stage checkpoint files (see
``pipeline/state.py``) as ``<work_dir>/run_manifest.json`` and does not
replace them — ``PipelineState`` remains the source of truth for stage data.
The manifest is a higher-level, operator-facing summary layered on top.

See ``docs/run-manifest-schema.md`` for the full schema documentation,
versioning policy, and backward-compatibility story.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .capability_result import CapabilityResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_WORK_DIR = ".pipeline"
_MANIFEST_FILENAME = "run_manifest.json"

# Bump only on a breaking change to the manifest shape (removing/renaming a
# field, changing a field's meaning). Additive fields do not require a bump.
# See docs/run-manifest-schema.md for the compatibility policy.
RUN_MANIFEST_SCHEMA_VERSION = 1

_LEGACY_RUN_ID = "legacy"


class RunOutcome(str, Enum):
    """Overall outcome of an operator run, mirroring capability statuses."""

    IN_PROGRESS = "in_progress"
    OK = "ok"
    WARNING = "warning"
    BLOCKED = "blocked"
    FAILED = "failed"


_VALID_OUTCOMES = {outcome.value for outcome in RunOutcome}


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _new_run_id() -> str:
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# RunManifest
# ---------------------------------------------------------------------------


class RunManifest:
    """Read/write the versioned run manifest for a pipeline work directory.

    Parameters
    ----------
    work_dir:
        Directory where ``run_manifest.json`` is stored (default ``.pipeline``,
        matching :class:`~tournament_scheduler.pipeline.state.PipelineState`).
    """

    def __init__(self, work_dir: str | os.PathLike[str] = _DEFAULT_WORK_DIR) -> None:
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self.work_dir / _MANIFEST_FILENAME

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_run(
        self,
        objective: str,
        *,
        input_fingerprint: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Start a new run, overwriting the previous manifest's run history.

        ``pending_questions`` is carried forward from any existing manifest
        rather than reset: escalation questions and their human answers are
        durable workspace state (see ``pipeline/escalation.py``), not
        per-run state — a question answered before an interruption must
        stay answered, and must survive across ``rvv-miniputt run``/
        ``operator run`` invocations for a human to actually be able to
        answer it in between.

        Returns the new manifest dict.
        """
        previous = self.read() if self.exists() else None
        carried_questions = (
            list(previous.get("pending_questions", [])) if isinstance(previous, dict) else []
        )
        now = _now_iso()
        manifest: dict[str, Any] = {
            "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
            "run_id": run_id or _new_run_id(),
            "objective": objective,
            "current_capability": None,
            "input_fingerprint": input_fingerprint or {},
            "started_at": now,
            "updated_at": now,
            "ended_at": None,
            "final_outcome": RunOutcome.IN_PROGRESS.value,
            "capabilities": [],
            "pending_questions": carried_questions,
        }
        self._write(manifest)
        return manifest

    def set_current_capability(self, name: str) -> None:
        """Record which capability is now active, without appending a result."""
        manifest = self.read()
        manifest["current_capability"] = name
        manifest["updated_at"] = _now_iso()
        self._write(manifest)

    def record_capability(self, result: CapabilityResult) -> dict[str, Any]:
        """Append a capability result to the run history.

        Returns the recorded entry (the result dict plus a ``recorded_at``
        timestamp).
        """
        manifest = self.read()
        entry = result.to_dict()
        entry["recorded_at"] = _now_iso()
        manifest.setdefault("capabilities", []).append(entry)
        if result.capability:
            manifest["current_capability"] = result.capability
        manifest["updated_at"] = entry["recorded_at"]
        self._write(manifest)
        return entry

    def finalize(self, outcome: str) -> None:
        """Mark the run as finished with a terminal outcome.

        *outcome* must be one of ``ok``, ``warning``, ``blocked``, ``failed``
        (not ``in_progress`` — use this only once the run has actually ended).
        """
        outcome_value = outcome.value if isinstance(outcome, RunOutcome) else str(outcome)
        if outcome_value not in _VALID_OUTCOMES or outcome_value == RunOutcome.IN_PROGRESS.value:
            raise ValueError(
                f"Invalid terminal outcome {outcome_value!r}. "
                f"Valid values: ok, warning, blocked, failed"
            )
        manifest = self.read()
        now = _now_iso()
        manifest["final_outcome"] = outcome_value
        manifest["updated_at"] = now
        manifest["ended_at"] = now
        self._write(manifest)

    # ------------------------------------------------------------------
    # Human escalation / approval protocol (pending_questions)
    # ------------------------------------------------------------------
    #
    # See pipeline/escalation.py for the Question shape and the types a
    # capability can raise. RunManifest only owns storage: append-if-new,
    # look up by id, and record an answer.

    def add_pending_question(self, question: dict[str, Any]) -> dict[str, Any]:
        """Append *question* (a dict from ``escalation.Question.to_dict()``)
        unless a question with the same ``id`` was already raised in this
        workspace, answered or not.

        Returns the newly stored question, or the existing entry when this
        exact question (same type/capability/summary, hence same id) has
        already been raised — so a capability can call this unconditionally
        every time it blocks without ever asking the same thing twice.
        """
        manifest = self.read()
        existing = manifest.setdefault("pending_questions", [])
        question_id = question.get("id")
        for entry in existing:
            if entry.get("id") == question_id:
                return entry
        existing.append(question)
        manifest["updated_at"] = _now_iso()
        self._write(manifest)
        return question

    def answer_question(
        self, question_id: str, answer: str, *, decided_by: str | None = None
    ) -> dict[str, Any]:
        """Record a durable human answer to a previously-raised question.

        Raises ``ValueError`` if no question with *question_id* exists.
        """
        manifest = self.read()
        for entry in manifest.get("pending_questions", []):
            if entry.get("id") == question_id:
                now = _now_iso()
                entry["answered"] = True
                entry["answer"] = answer
                entry["decided_by"] = decided_by
                entry["decided_at"] = now
                manifest["updated_at"] = now
                self._write(manifest)
                return entry
        raise ValueError(f"No pending question with id {question_id!r} in {self.path}")

    def unanswered_questions(self) -> list[dict[str, Any]]:
        """Return every question in this workspace that has no recorded answer."""
        return [q for q in self.read().get("pending_questions", []) if not q.get("answered")]

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read(self) -> dict[str, Any]:
        """Return the current manifest.

        When no manifest file exists yet (e.g. the work directory was
        populated by a version of the pipeline that predates this schema),
        a read-only manifest is synthesized from the legacy stage checkpoint
        files so callers always get a consistent shape.
        """
        if not self.path.exists():
            return self._synthesize_from_legacy_checkpoints()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._synthesize_from_legacy_checkpoints()
        if not isinstance(data, dict):
            return self._synthesize_from_legacy_checkpoints()
        return data

    def exists(self) -> bool:
        return self.path.exists()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write(self, manifest: dict[str, Any]) -> None:
        try:
            self.path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"Failed to write run manifest {self.path}: {exc}") from exc

    def _synthesize_from_legacy_checkpoints(self) -> dict[str, Any]:
        """Build a manifest-shaped view from ``stage*.json`` checkpoints.

        This is the backward-compatibility path required for work
        directories that were populated before ``run_manifest.json`` existed:
        every field the manifest promises is still populated, just derived
        from data that was already on disk.
        """
        from .state import PipelineState, StageName

        state = PipelineState(self.work_dir)
        capabilities: list[dict[str, Any]] = []
        current_capability: str | None = None
        latest_updated: str | None = None
        earliest_updated: str | None = None
        any_failed = False
        any_incomplete = False

        for stage in (StageName.CONFIG, StageName.SCRAPING, StageName.PLANNING, StageName.EXPORT):
            checkpoint_path = state.checkpoint_path(stage)
            if not checkpoint_path.exists():
                continue

            envelope = state.read_envelope(stage)
            stage_status = str(envelope.get("status", "pending"))
            is_stale = bool(envelope.get("stale"))

            if stage_status == "done" and not is_stale:
                capability_status = "ok"
            elif stage_status == "failed":
                capability_status = "failed"
                any_failed = True
            else:
                capability_status = "warning"
                any_incomplete = True

            summary = f"Legacy checkpoint for stage '{stage.value}' (status={stage_status})"
            if is_stale:
                summary += f", stale: {envelope.get('stale_reason', '')}"

            result = CapabilityResult(
                status=capability_status,
                summary=summary,
                capability=stage.value,
                problems=[str(envelope["error"])] if envelope.get("error") else [],
            )
            entry = result.to_dict()
            entry["recorded_at"] = envelope.get("updated_at", "")
            capabilities.append(entry)

            current_capability = stage.value
            updated_at = envelope.get("updated_at")
            if updated_at:
                if latest_updated is None or updated_at > latest_updated:
                    latest_updated = updated_at
                if earliest_updated is None or updated_at < earliest_updated:
                    earliest_updated = updated_at

        if not capabilities:
            final_outcome = RunOutcome.IN_PROGRESS.value
        elif any_failed:
            final_outcome = RunOutcome.FAILED.value
        elif any_incomplete or len(capabilities) < 4:
            final_outcome = RunOutcome.WARNING.value
        else:
            final_outcome = RunOutcome.OK.value

        return {
            "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
            "run_id": _LEGACY_RUN_ID,
            "objective": None,
            "current_capability": current_capability,
            "input_fingerprint": {},
            "started_at": earliest_updated,
            "updated_at": latest_updated,
            "ended_at": None,
            "final_outcome": final_outcome,
            "capabilities": capabilities,
            "pending_questions": [],
            "synthesized_from_legacy_checkpoints": True,
        }
