"""Structured capability-result contract for the AI operator.

A *capability* is any unit of operator-visible work — a pipeline stage, a
recovery action, a source-health check, a plan comparison, and so on.  Rather
than returning only console text or a bare success/failure flag, a capability
should return a :class:`CapabilityResult` so an agent (or a human reading one
JSON blob) can answer, without parsing logs:

- What happened?
- What evidence supports the result?
- How confident is the system?
- What artifacts were produced?
- What problems were encountered?
- What should happen next?
- Does this require a human decision?

See ``docs/run-manifest-schema.md`` for the full contract and versioning
policy, and ``docs/ai-operator-product-direction.md`` for the product
rationale.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .operator_action import OperatorAction

# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

# Bump only on a breaking change to the CapabilityResult shape. Additive
# fields (new optional keys with safe defaults) do not require a bump.
CAPABILITY_RESULT_SCHEMA_VERSION = 1


class CapabilityStatus(str, Enum):
    """Outcome of a capability invocation."""

    OK = "ok"
    WARNING = "warning"
    BLOCKED = "blocked"
    FAILED = "failed"


_VALID_STATUSES = {status.value for status in CapabilityStatus}


@dataclass
class CapabilityResult:
    """Structured outcome of a single capability invocation.

    Parameters
    ----------
    status:
        One of ``ok``, ``warning``, ``blocked``, ``failed``.
    summary:
        One or two sentence human-readable description of what happened.
    evidence:
        Concrete facts backing the result (counts, file paths, comparisons).
        Free-form strings or small dicts — whatever supports the summary.
    confidence:
        A 0.0-1.0 estimate of how much the result should be trusted. Purely
        informational; nothing enforces a threshold.
    artifacts:
        Paths or identifiers of files/checkpoints produced by the capability.
    problems:
        Concrete issues encountered, even when ``status`` is ``ok`` (e.g. a
        non-fatal warning worth surfacing).
    suggested_actions:
        Concrete next steps an operator (human or agent) could take, as
        human-readable prose.
    requires_human:
        True when this result cannot be resolved without human judgment,
        credentials, or authorization.
    capability:
        Name of the capability that produced this result (e.g.
        ``"stage2_scraping"``). Optional — callers that already track this
        out-of-band (such as a dict keyed by capability name) may leave it
        blank.
    actions:
        The same next steps as ``suggested_actions``, but machine-callable:
        a list of :class:`~tournament_scheduler.pipeline.operator_action.OperatorAction`.
        Optional and purely additive — ``suggested_actions`` remains the
        human-readable form and existing consumers of it are unaffected.
    """

    status: str
    summary: str = ""
    evidence: list[Any] = field(default_factory=list)
    confidence: float = 1.0
    artifacts: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    suggested_actions: list[str] = field(default_factory=list)
    requires_human: bool = False
    capability: str = ""
    actions: "list[OperatorAction]" = field(default_factory=list)

    def __post_init__(self) -> None:
        status_value = self.status.value if isinstance(self.status, CapabilityStatus) else str(self.status)
        if status_value not in _VALID_STATUSES:
            raise ValueError(
                f"Invalid capability status {status_value!r}. "
                f"Valid values: {', '.join(sorted(_VALID_STATUSES))}"
            )
        self.status = status_value
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

    # ------------------------------------------------------------------
    # Convenience constructors
    # ------------------------------------------------------------------

    @classmethod
    def ok(cls, summary: str, **kwargs: Any) -> "CapabilityResult":
        return cls(status=CapabilityStatus.OK.value, summary=summary, **kwargs)

    @classmethod
    def warning(cls, summary: str, **kwargs: Any) -> "CapabilityResult":
        return cls(status=CapabilityStatus.WARNING.value, summary=summary, **kwargs)

    @classmethod
    def blocked(cls, summary: str, **kwargs: Any) -> "CapabilityResult":
        kwargs.setdefault("requires_human", True)
        return cls(status=CapabilityStatus.BLOCKED.value, summary=summary, **kwargs)

    @classmethod
    def failed(cls, summary: str, **kwargs: Any) -> "CapabilityResult":
        return cls(status=CapabilityStatus.FAILED.value, summary=summary, **kwargs)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CAPABILITY_RESULT_SCHEMA_VERSION,
            "capability": self.capability,
            "status": self.status,
            "summary": self.summary,
            "evidence": list(self.evidence),
            "confidence": self.confidence,
            "artifacts": list(self.artifacts),
            "problems": list(self.problems),
            "suggested_actions": list(self.suggested_actions),
            "requires_human": self.requires_human,
            "actions": [action.to_dict() for action in self.actions],
        }

    def to_json(self, **kwargs: Any) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, **kwargs)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapabilityResult":
        """Build a :class:`CapabilityResult` from a dict, ignoring unknown keys.

        Unknown/future fields are dropped rather than rejected so a manifest
        written by a newer schema version can still be read by older code.
        """
        from .operator_action import OperatorAction

        return cls(
            status=data.get("status", CapabilityStatus.FAILED.value),
            summary=data.get("summary", ""),
            evidence=list(data.get("evidence", []) or []),
            confidence=float(data.get("confidence", 1.0) or 0.0),
            artifacts=list(data.get("artifacts", []) or []),
            problems=list(data.get("problems", []) or []),
            suggested_actions=list(data.get("suggested_actions", []) or []),
            requires_human=bool(data.get("requires_human", False)),
            capability=data.get("capability", ""),
            actions=[OperatorAction.from_dict(a) for a in (data.get("actions") or []) if isinstance(a, dict)],
        )

    @property
    def is_terminal_success(self) -> bool:
        """True when the capability completed without blocking further work."""
        return self.status in (CapabilityStatus.OK.value, CapabilityStatus.WARNING.value)
