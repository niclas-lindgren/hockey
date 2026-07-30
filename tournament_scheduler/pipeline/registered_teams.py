"""Standalone public registered-team overview generation.

The SharePoint export used here may contain private/internal columns.  This
module intentionally projects only ``club``, ``label`` and ``age_group`` into
public artifacts; validation/source metadata stays in the private validation
report.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PUBLIC_COLUMNS: tuple[str, ...] = ("club", "label", "age_group")
_SCHEMA_VERSION = 1
_WHITESPACE_RE = re.compile(r"\s+")


class RegisteredTeamsValidationError(ValueError):
    """Raised when a registered-team CSV cannot be safely rendered."""

    def __init__(self, errors: list[str], report: dict[str, Any]):
        super().__init__("; ".join(errors))
        self.errors = errors
        self.report = report


def build_registered_teams_payload(
    csv_path: str | Path,
    *,
    config_path: str | Path | None = None,
    generated_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ``(public_payload, validation_report)`` for a SharePoint CSV.

    Public output contains only ``club``, ``label`` and ``age_group`` plus
    aggregate counts.  Extra CSV columns are ignored and recorded in the
    validation report.  A header-only CSV is valid and produces an empty page
    payload.
    """
    source = Path(csv_path)
    if not source.exists():
        report = _base_report(source, [], [], [], [], config_path=config_path)
        errors = [f"Filen finnes ikke: {source}"]
        report["errors"] = errors
        report["error_count"] = len(errors)
        raise RegisteredTeamsValidationError(errors, report)

    raw_bytes = source.read_bytes()
    source_fingerprint = hashlib.sha256(raw_bytes).hexdigest()
    text = raw_bytes.decode("utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    raw_headers = list(reader.fieldnames or [])
    header_by_canonical = {_canonical_header(header): header for header in raw_headers}
    included_columns = [header_by_canonical[column] for column in PUBLIC_COLUMNS if column in header_by_canonical]
    excluded_columns = [header for header in raw_headers if _canonical_header(header) not in PUBLIC_COLUMNS]

    errors: list[str] = []
    warnings: list[str] = []
    missing_columns = [column for column in PUBLIC_COLUMNS if column not in header_by_canonical]
    for column in missing_columns:
        errors.append(f"Mangler påkrevd kolonne: {column}")

    configured_age_groups = _load_configured_age_groups(config_path)
    rows: list[dict[str, str]] = []
    seen: dict[tuple[str, str, str], int] = {}

    if not missing_columns:
        for index, raw_row in enumerate(reader, start=2):
            row = {
                column: _normalize_value(raw_row.get(header_by_canonical[column], ""))
                for column in PUBLIC_COLUMNS
            }
            for column, value in row.items():
                if not value:
                    errors.append(f"Rad {index}: '{column}' mangler verdi.")
            if configured_age_groups and row["age_group"] and row["age_group"] not in configured_age_groups:
                errors.append(
                    f"Rad {index}: aldersgruppen '{row['age_group']}' finnes ikke i konfigurert age_groups."
                )
            if all(row.values()):
                key = tuple(_dedupe_key(row[column]) for column in PUBLIC_COLUMNS)
                if key in seen:
                    errors.append(
                        f"Rad {index}: duplikat av rad {seen[key]} for club+label+age_group "
                        f"({row['club']} / {row['label']} / {row['age_group']})."
                    )
                else:
                    seen[key] = index
                rows.append(row)

    if excluded_columns:
        warnings.append(
            "Ignorerte ekstra kolonner som ikke publiseres: " + ", ".join(sorted(excluded_columns, key=str.casefold))
        )

    report = _base_report(
        source,
        raw_headers,
        included_columns,
        excluded_columns,
        warnings,
        config_path=config_path,
    )
    report.update(
        {
            "source_sha256": source_fingerprint,
            "row_count": len(rows),
            "configured_age_groups": configured_age_groups,
            "errors": errors,
            "error_count": len(errors),
        }
    )
    if errors:
        raise RegisteredTeamsValidationError(errors, report)

    generated = generated_at or _utc_now()
    payload = _build_public_payload(rows, configured_age_groups=configured_age_groups, generated_at=generated)
    return payload, report


def _build_public_payload(
    rows: Iterable[dict[str, str]],
    *,
    configured_age_groups: list[str],
    generated_at: str,
) -> dict[str, Any]:
    grouped: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    clubs: set[str] = set()
    total_teams = 0
    for row in rows:
        grouped[row["age_group"]][row["club"]].add(row["label"])
        clubs.add(row["club"])
        total_teams += 1

    age_order = {age_group: index for index, age_group in enumerate(configured_age_groups)}

    def age_sort_key(age_group: str) -> tuple[int, int | str, str]:
        if age_group in age_order:
            return (0, age_order[age_group], age_group.casefold())
        match = re.fullmatch(r"(J?U)(\d+)", age_group, flags=re.IGNORECASE)
        if match:
            prefix = match.group(1).upper()
            return (1, int(match.group(2)), prefix)
        return (2, age_group.casefold(), age_group)

    age_groups = []
    for age_group in sorted(grouped, key=age_sort_key):
        club_entries = []
        team_count = 0
        for club in sorted(grouped[age_group], key=str.casefold):
            teams = sorted(grouped[age_group][club], key=str.casefold)
            team_count += len(teams)
            club_entries.append({"club": club, "team_count": len(teams), "teams": teams})
        age_groups.append(
            {
                "age_group": age_group,
                "team_count": team_count,
                "club_count": len(club_entries),
                "clubs": club_entries,
            }
        )

    return {
        "schema_version": _SCHEMA_VERSION,
        "generated_at": generated_at,
        "title": "Påmeldte lag",
        "total_teams": total_teams,
        "total_clubs": len(clubs),
        "age_groups": age_groups,
    }


def _base_report(
    source: Path,
    raw_headers: list[str],
    included_columns: list[str],
    excluded_columns: list[str],
    warnings: list[str],
    *,
    config_path: str | Path | None,
) -> dict[str, Any]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "source_file": source.name,
        "source_sha256": None,
        "config_file": Path(config_path).name if config_path else None,
        "required_columns": list(PUBLIC_COLUMNS),
        "input_columns": raw_headers,
        "included_columns": included_columns,
        "excluded_columns": excluded_columns,
        "privacy_note": "Kun club, label og age_group brukes i offentlige artefakter.",
        "warnings": warnings,
        "errors": [],
        "error_count": 0,
        "row_count": 0,
    }


def _load_configured_age_groups(config_path: str | Path | None) -> list[str]:
    if not config_path:
        return []
    path = Path(config_path)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return []
    groups = data.get("age_groups")
    if not isinstance(groups, list):
        return []
    return [_normalize_value(group) for group in groups if _normalize_value(group)]


def _canonical_header(value: Any) -> str:
    return _normalize_value(value).casefold().lstrip("\ufeff")


def _normalize_value(value: Any) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "").strip())


def _dedupe_key(value: str) -> str:
    return _normalize_value(value).casefold()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
