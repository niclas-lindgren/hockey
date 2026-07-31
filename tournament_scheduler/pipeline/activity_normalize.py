"""Normalize SharePoint activity snapshots into canonical repository input.

The SharePoint year-wheel export uses compact Norwegian dates such as
``15.12.``.  The repository's canonical activity snapshot must instead be
self-contained, so those values are rewritten to ISO ``YYYY-MM-DD`` dates
before validation and publication.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

_PARTIAL_DATE_RE = re.compile(r"^(\d{1,2})[./-](\d{1,2})[.]?$")
_DATE_HEADERS = {"date", "dato", "dag", "når", "nar", "when"}


def normalize_activity_json(path: str | Path, *, year: int) -> bool:
    """Rewrite compact dates in a schema-v1 activity snapshot in place.

    Returns ``True`` when the file changed. Only cells in columns whose header
    is a recognised date label are considered, so unrelated numeric text is
    never rewritten.
    """
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    values = payload.get("values")
    if not isinstance(values, list):
        return False

    date_columns = _find_date_columns(values)
    if not date_columns:
        return False

    changed = False
    for row in values:
        if not isinstance(row, list):
            continue
        for column in date_columns:
            if column >= len(row) or not isinstance(row[column], str):
                continue
            text = row[column].strip()
            match = _PARTIAL_DATE_RE.fullmatch(text)
            if not match:
                continue
            day = int(match.group(1))
            month = int(match.group(2))
            try:
                normalized = date(year, month, day).isoformat()
            except ValueError:
                continue
            if row[column] != normalized:
                row[column] = normalized
                changed = True

    if changed:
        source.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return changed


def _find_date_columns(values: list[list[Any]]) -> set[int]:
    """Return all recognised date-column indexes from the first header row."""
    for row in values:
        if not isinstance(row, list):
            continue
        columns = {
            index
            for index, value in enumerate(row)
            if _normalize_header(value) in _DATE_HEADERS
        }
        if columns:
            return columns
    return set()


def _normalize_header(value: Any) -> str:
    return str(value or "").strip().lower()
