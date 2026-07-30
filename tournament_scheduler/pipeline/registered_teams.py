"""Standalone public registered-team overview generation.

The SharePoint export used here may contain private/internal columns.  This
module intentionally projects only ``club``, ``label`` and ``age_group`` into
public artifacts; validation/source metadata stays in the private validation
report.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PUBLIC_COLUMNS: tuple[str, ...] = ("club", "label", "age_group")
DEFAULT_REGISTERED_TEAMS_DIR = "registered-teams"
REGISTERED_TEAMS_HTML = "pameldte-lag.html"
REGISTERED_TEAMS_JSON = "pameldte-lag.json"
REGISTERED_TEAMS_VALIDATION_REPORT = "validation-report.json"
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


def generate_registered_team_artifacts(
    *,
    csv_path: str | Path,
    export_dir: str | Path = "export",
    config_path: str | Path | None = None,
    generated_at: str | None = None,
) -> dict[str, str]:
    """Validate *csv_path* and write public/review registered-team artifacts."""
    payload, report = build_registered_teams_payload(
        csv_path,
        config_path=config_path,
        generated_at=generated_at,
    )
    target_dir = Path(export_dir) / DEFAULT_REGISTERED_TEAMS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    json_path = target_dir / REGISTERED_TEAMS_JSON
    validation_path = target_dir / REGISTERED_TEAMS_VALIDATION_REPORT
    html_path = target_dir / REGISTERED_TEAMS_HTML

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    validation_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    html_path.write_text(render_registered_teams_html(payload), encoding="utf-8")

    return {
        "registered_teams_html": str(html_path),
        "registered_teams_json": str(json_path),
        "registered_teams_validation_report": str(validation_path),
    }


def render_registered_teams_html(payload: dict[str, Any]) -> str:
    """Render a static, accessible Norwegian page from a public payload."""
    age_groups = payload.get("age_groups", []) or []
    generated_at = _format_generated_at(str(payload.get("generated_at", "")))
    total_teams = int(payload.get("total_teams", 0) or 0)
    total_clubs = int(payload.get("total_clubs", 0) or 0)

    if not age_groups:
        content = (
            '<section class="empty-state">'
            '<h2>Ingen lag er registrert ennå</h2>'
            '<p>Oversikten oppdateres fortløpende når påmeldinger er godkjent.</p>'
            '</section>'
        )
    else:
        sections = []
        for group in age_groups:
            clubs = []
            for club in group.get("clubs", []) or []:
                teams = "".join(f"<li>{_e(team)}</li>" for team in club.get("teams", []) or [])
                clubs.append(
                    '<article class="club-card">'
                    f'<h3>{_e(club.get("club", ""))}</h3>'
                    f'<p>{int(club.get("team_count", 0) or 0)} lag</p>'
                    f'<ul>{teams}</ul>'
                    '</article>'
                )
            sections.append(
                '<section class="age-group-card">'
                '<div class="age-group-card__head">'
                f'<h2>{_e(group.get("age_group", ""))}</h2>'
                f'<span>{int(group.get("team_count", 0) or 0)} lag · {int(group.get("club_count", 0) or 0)} klubber</span>'
                '</div>'
                f'<div class="club-grid">{"".join(clubs)}</div>'
                '</section>'
            )
        content = "\n".join(sections)

    return f"""<!doctype html>
<html lang="nb">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Påmeldte lag</title>
<style>
  :root {{ --bg:#f7fafc; --surface:#ffffff; --ink:#102033; --muted:#5b6f84; --line:#d7e2ec; --accent:#0b66c3; --accent-soft:#e5f1fc; --shadow:0 18px 45px rgba(15,23,42,.10); --radius:18px; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:radial-gradient(circle at top left,#dceffd,transparent 28rem),var(--bg); color:var(--ink); line-height:1.5; }}
  .wrap {{ width:min(1120px,100%); margin:0 auto; padding:clamp(16px,3vw,32px); }}
  header {{ display:grid; gap:10px; margin-bottom:24px; }}
  .eyebrow {{ color:#07477f; font-size:13px; font-weight:850; letter-spacing:.08em; text-transform:uppercase; }}
  h1 {{ margin:0; font-size:clamp(32px,5vw,54px); letter-spacing:-.045em; line-height:1.03; }}
  .lead {{ max-width:780px; margin:0; color:var(--muted); font-size:clamp(15px,2vw,18px); }}
  .meta-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin:22px 0; }}
  .metric, .age-group-card, .empty-state {{ background:rgba(255,255,255,.9); border:1px solid var(--line); border-radius:var(--radius); box-shadow:var(--shadow); }}
  .metric {{ padding:16px; }}
  .metric span {{ display:block; color:var(--muted); font-size:13px; font-weight:800; text-transform:uppercase; letter-spacing:.04em; }}
  .metric strong {{ display:block; margin-top:4px; font-size:clamp(24px,4vw,36px); letter-spacing:-.04em; }}
  .age-group-stack {{ display:grid; gap:16px; }}
  .age-group-card {{ overflow:hidden; }}
  .age-group-card__head {{ display:flex; align-items:center; justify-content:space-between; gap:12px; padding:18px 20px; border-bottom:1px solid var(--line); background:linear-gradient(180deg,#fff,var(--accent-soft)); }}
  .age-group-card h2 {{ margin:0; font-size:24px; }}
  .age-group-card__head span {{ color:#07477f; font-weight:850; }}
  .club-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:12px; padding:16px; }}
  .club-card {{ border:1px solid var(--line); border-radius:14px; background:var(--surface); padding:14px; }}
  .club-card h3 {{ margin:0 0 2px; font-size:17px; }}
  .club-card p {{ margin:0 0 10px; color:var(--muted); font-weight:750; }}
  .club-card ul {{ margin:0; padding-left:20px; }}
  .club-card li {{ margin:2px 0; }}
  .empty-state {{ padding:32px; text-align:center; }}
  .empty-state h2 {{ margin:0 0 8px; }}
  .empty-state p {{ margin:0; color:var(--muted); }}
  footer {{ margin-top:24px; color:var(--muted); font-size:14px; }}
  a {{ color:var(--accent); font-weight:800; }}
  @media (max-width:720px) {{ .meta-grid {{ grid-template-columns:1fr; }} .age-group-card__head {{ align-items:flex-start; flex-direction:column; }} }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="eyebrow">RVV Hockey</div>
    <h1>Påmeldte lag</h1>
    <p class="lead">Offentlig oversikt over godkjente lagpåmeldinger. Påmeldingene kan endre seg frem til påmeldingsfristen, og siden oppdateres når nye lag er godkjent.</p>
  </header>

  <section class="meta-grid" aria-label="Nøkkeltall">
    <div class="metric"><span>Lag totalt</span><strong>{total_teams}</strong></div>
    <div class="metric"><span>Klubber</span><strong>{total_clubs}</strong></div>
    <div class="metric"><span>Aldersgrupper</span><strong>{len(age_groups)}</strong></div>
  </section>

  <main class="age-group-stack">
    {content}
  </main>

  <footer>
    Sist oppdatert: <time datetime="{_e(str(payload.get('generated_at', '')))}">{_e(generated_at)}</time>.
    Personopplysninger, kontaktfelt, SharePoint-ID-er, interne statuser og kommentarer publiseres ikke.
    <a href="pameldte-lag.json">Last ned offentlig JSON</a>.
  </footer>
</div>
</body>
</html>
"""


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


def _format_generated_at(value: str) -> str:
    if not value:
        return "ukjent tidspunkt"
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return value
    return moment.strftime("%Y-%m-%d %H:%M UTC")


def _e(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _canonical_header(value: Any) -> str:
    return _normalize_value(value).casefold().lstrip("\ufeff")


def _normalize_value(value: Any) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "").strip())


def _dedupe_key(value: str) -> str:
    return _normalize_value(value).casefold()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
