"""Human escalation and approval protocol.

Defines the escalation types an AI operator capability can raise, and the
durable question/answer record stored in the run manifest's
``pending_questions`` list (see ``docs/run-manifest-schema.md``).

A question is identified by a stable id derived from
``(type, capability, summary)``, so the exact same question is never asked
twice in a workspace: recording an answer makes it a durable, auditable
decision, and a later run that would raise the identical question finds it
already answered instead of blocking again. This is deliberately scoped to
*identical* questions — a genuinely different problem (different summary)
always gets its own id and is escalated normally.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

from .fingerprints import stable_payload_sha256
from .run_manifest import RunManifest

if TYPE_CHECKING:
    from .capability_result import CapabilityResult


class EscalationType(str, Enum):
    """Reasons an operator capability may need a human decision."""

    CREDENTIALS = "credentials"
    INCOMPLETE_DATA = "incomplete_data"
    AMBIGUOUS_POLICY = "ambiguous_policy"
    DESTRUCTIVE_REPAIR = "destructive_repair"
    IMPOSSIBLE_CONSTRAINTS = "impossible_constraints"
    EXTERNAL_PUBLICATION = "external_publication"


_VALID_TYPES = {t.value for t in EscalationType}


def _question_id(escalation_type: str, capability: str, summary: str) -> str:
    return stable_payload_sha256(
        {"type": escalation_type, "capability": capability, "summary": summary}
    )[:16]


@dataclass
class Question:
    """A single escalation, with enough structure to answer it without
    re-deriving context: what happened, what could be done about it, what
    the operator recommends, and what's at stake either way.
    """

    type: str
    capability: str
    summary: str
    context: str = ""
    alternatives: list[str] = field(default_factory=list)
    recommendation: str = ""
    impact: str = ""

    def __post_init__(self) -> None:
        type_value = self.type.value if isinstance(self.type, EscalationType) else str(self.type)
        if type_value not in _VALID_TYPES:
            raise ValueError(
                f"Invalid escalation type {type_value!r}. Valid values: {', '.join(sorted(_VALID_TYPES))}"
            )
        self.type = type_value

    @property
    def id(self) -> str:
        return _question_id(self.type, self.capability, self.summary)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "capability": self.capability,
            "summary": self.summary,
            "context": self.context,
            "alternatives": list(self.alternatives),
            "recommendation": self.recommendation,
            "impact": self.impact,
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "answered": False,
            "answer": None,
            "decided_by": None,
            "decided_at": None,
        }


def raise_question(work_dir: str, question: Question) -> dict[str, Any]:
    """Record *question* in the run manifest, deduplicated by stable id.

    Returns the stored entry — either the newly added question, or the
    existing entry (answered or not) when this exact question was already
    raised in this workspace.
    """
    return RunManifest(work_dir).add_pending_question(question.to_dict())


def answer_question(
    work_dir: str, question_id: str, answer: str, *, decided_by: str | None = None
) -> dict[str, Any]:
    """Record a durable human answer to a previously-raised question."""
    return RunManifest(work_dir).answer_question(question_id, answer, decided_by=decided_by)


def unanswered_questions(work_dir: str) -> list[dict[str, Any]]:
    """Return every pending (not yet answered) question for this workspace."""
    return RunManifest(work_dir).unanswered_questions()


_CREDENTIAL_MARKERS = ("legitimasjon", "credential", "miljøvariable")
_IMPOSSIBLE_MARKERS = ("kollisjon", "ingen gyldig plan", "0 turneringer", "klarte ikke")
_POLICY_MARKERS = ("godkjenning", "approval")


def infer_escalation_type(result: "CapabilityResult") -> str:
    """Best-effort classification of *why* a blocked capability needs a human.

    A coarse keyword heuristic over the capability's own problems/suggested
    actions, not a hard rule — capabilities that know their own escalation
    reason should pass an explicit :class:`EscalationType` to
    :func:`from_capability_result` instead of relying on this.
    """
    text = " ".join(result.problems + result.suggested_actions).lower()
    if any(marker in text for marker in _CREDENTIAL_MARKERS):
        return EscalationType.CREDENTIALS.value
    if any(marker in text for marker in _IMPOSSIBLE_MARKERS):
        return EscalationType.IMPOSSIBLE_CONSTRAINTS.value
    if any(marker in text for marker in _POLICY_MARKERS):
        return EscalationType.AMBIGUOUS_POLICY.value
    return EscalationType.INCOMPLETE_DATA.value


def from_capability_result(
    result: "CapabilityResult", *, escalation_type: str | None = None, impact: str = ""
) -> Question:
    """Build a :class:`Question` from a blocked :class:`CapabilityResult`.

    Reuses fields the capability already populated: ``evidence`` becomes
    context, ``suggested_actions`` become alternatives (the first one doubles
    as the recommendation), and ``problems`` become the impact when *impact*
    is not given explicitly. This lets most blocked capabilities raise a
    well-formed question without writing bespoke escalation code — only
    capabilities with a genuinely ambiguous cause need to pass an explicit
    *escalation_type*.
    """
    resolved_type = escalation_type or infer_escalation_type(result)
    alternatives = list(result.suggested_actions)
    return Question(
        type=resolved_type,
        capability=result.capability or "unknown",
        summary=result.summary,
        context="; ".join(result.evidence) if result.evidence else result.summary,
        alternatives=alternatives,
        recommendation=alternatives[0] if alternatives else "",
        impact=impact or "; ".join(result.problems),
    )
