"""Shared typed DTOs for the application layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


_QUESTION_FIELDS = {
    "id",
    "type",
    "capability",
    "summary",
    "context",
    "alternatives",
    "recommendation",
    "impact",
    "scope",
    "scope_key",
    "created_at",
    "answered",
    "answer",
    "decided_by",
    "decided_at",
    "stale",
    "stale_reason",
    "promoted_from",
    "promoted_at",
}


@dataclass(frozen=True)
class OperatorQuestion:
    """A typed view of a durable operator escalation question."""

    id: str
    type: str
    capability: str
    summary: str
    context: str = ""
    alternatives: tuple[str, ...] = ()
    recommendation: str = ""
    impact: str = ""
    scope: str = "workspace"
    scope_key: str = ""
    created_at: str | None = None
    answered: bool = False
    answer: str | None = None
    decided_by: str | None = None
    decided_at: str | None = None
    stale: bool = False
    stale_reason: str | None = None
    promoted_from: str | None = None
    promoted_at: str | None = None
    extra: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "OperatorQuestion":
        alternatives = data.get("alternatives") or []
        return cls(
            id=str(data.get("id") or ""),
            type=str(data.get("type") or ""),
            capability=str(data.get("capability") or ""),
            summary=str(data.get("summary") or ""),
            context=str(data.get("context") or ""),
            alternatives=tuple(str(item) for item in alternatives),
            recommendation=str(data.get("recommendation") or ""),
            impact=str(data.get("impact") or ""),
            scope=str(data.get("scope") or "workspace"),
            scope_key=str(data.get("scope_key") or ""),
            created_at=_optional_str(data.get("created_at")),
            answered=bool(data.get("answered", False)),
            answer=_optional_str(data.get("answer")),
            decided_by=_optional_str(data.get("decided_by")),
            decided_at=_optional_str(data.get("decided_at")),
            stale=bool(data.get("stale", False)),
            stale_reason=_optional_str(data.get("stale_reason")),
            promoted_from=_optional_str(data.get("promoted_from")),
            promoted_at=_optional_str(data.get("promoted_at")),
            extra={key: value for key, value in data.items() if key not in _QUESTION_FIELDS},
        )

    def to_dict(self) -> dict[str, Any]:
        payload = dict(self.extra)
        payload.update(
            {
                "id": self.id,
                "type": self.type,
                "capability": self.capability,
                "summary": self.summary,
                "context": self.context,
                "alternatives": list(self.alternatives),
                "recommendation": self.recommendation,
                "impact": self.impact,
                "scope": self.scope,
                "scope_key": self.scope_key,
                "created_at": self.created_at,
                "answered": self.answered,
                "answer": self.answer,
                "decided_by": self.decided_by,
                "decided_at": self.decided_at,
                "stale": self.stale,
                "stale_reason": self.stale_reason,
                "promoted_from": self.promoted_from,
                "promoted_at": self.promoted_at,
            }
        )
        return payload


@dataclass(frozen=True)
class OperatorHealth:
    """Result from the operator-state manifest health use case."""

    healthy: bool
    writable: bool
    detail: str = ""
    manifest_recovery: Mapping[str, Any] | None = None
    extra: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "OperatorHealth":
        return cls(
            healthy=bool(data.get("healthy", False)),
            writable=bool(data.get("writable", False)),
            detail=str(data.get("detail") or ""),
            manifest_recovery=data.get("manifest_recovery"),
            extra={
                key: value
                for key, value in data.items()
                if key not in {"healthy", "writable", "detail", "manifest_recovery"}
            },
        )

    def to_dict(self) -> dict[str, Any]:
        payload = dict(self.extra)
        payload.update(
            {
                "healthy": self.healthy,
                "writable": self.writable,
                "manifest_recovery": self.manifest_recovery,
                "detail": self.detail,
            }
        )
        return payload

    @property
    def exit_code(self) -> int:
        return 0 if self.healthy else 1


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
