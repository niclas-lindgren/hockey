"""Operator-state application use cases.

This module is the first typed slice of the application layer requested by
GitHub issue #44. It wraps durable pipeline state APIs in small in-process
functions that transports can call without owning the policy themselves.
"""

from __future__ import annotations

from .dto import OperatorHealth, OperatorQuestion
from ..pipeline.escalation import (
    all_questions,
    answer_question,
    promote_question,
    unanswered_questions,
)
from ..pipeline.run_manifest import RunManifest


def list_operator_questions(work_dir: str, *, include_all: bool = False) -> list[OperatorQuestion]:
    """Return operator escalation questions for *work_dir*.

    By default this returns only unanswered questions. ``include_all=True``
    returns the audit trail, including answered and stale questions.
    """

    raw_questions = all_questions(work_dir) if include_all else unanswered_questions(work_dir)
    return [OperatorQuestion.from_dict(question) for question in raw_questions]


def record_operator_answer(
    work_dir: str,
    question_id: str,
    answer: str,
    *,
    decided_by: str | None = None,
) -> OperatorQuestion:
    """Record a durable answer to a previously-raised operator question."""

    return OperatorQuestion.from_dict(
        answer_question(work_dir, question_id, answer, decided_by=decided_by)
    )


def promote_operator_question(
    work_dir: str,
    question_id: str,
    scope: str,
    *,
    scope_key: str = "",
    decided_by: str | None = None,
) -> OperatorQuestion:
    """Promote an answered operator question to a broader decision scope."""

    return OperatorQuestion.from_dict(
        promote_question(
            work_dir,
            question_id,
            scope,
            new_scope_key=scope_key,
            decided_by=decided_by,
        )
    )


def check_operator_health(work_dir: str) -> OperatorHealth:
    """Check whether the operator run manifest is readable and writable."""

    return OperatorHealth.from_dict(RunManifest(work_dir).check_health())
