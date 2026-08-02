"""Standalone public registered-team overview generation.

The SharePoint export used here may contain private/internal columns. This
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
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .activity_publish import copy_latest_snapshot

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


class RegisteredTeamsPublishError(RuntimeError):
    """Raised when a registered-team publish staging snapshot cannot be prepared."""


def default_registered_teams_run_id(now: datetime | None = None) -> str:
    """Return a stable run id prefix for registered-team publishes."""
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)
    return f"registered-teams-{moment.strftime('%Y%m%dT%H%M%SZ')}"


def build_registered_teams_payload(
    csv_path: str | Path,
    *,
    config_path: str | Path | None = None,
    generated_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ``(public_payload, validation_report)`` for a SharePoint CSV."""
    source = Path(csv_path)
    if not source.exists():
        report = _base_report(source, [], [], [], [], config_path=config_path)
        errors = [f"Filen finnes ikke: {source}"]
        report["errors"] = errors
        report["error_count"] = len(errors)
        raise RegisteredTeamsValidationError(errors, report)

    raw_bytes = source.read_bytes()
    source_fingerprint = hashlib.sha256(raw_bytes).hexdigest()
    reader = csv.DictReader(raw_bytes.decode("utf-8-sig").splitlines())
    raw_headers = list(reader.fieldnames or [])
    header_by_canonical = {_canonical_header(header): header for header in raw_headers}
    included_columns = [header_by_canonical[column] for column in PUBLIC_COLUMNS if column in header_by_canonical]
    excluded_columns = [header for header in raw_headers if _canonical_header(header) not in PUBLIC_COLUMNS]

    errors: list[str] = []
    warnings: list[str] = []
    missing_columns = [column for column in PUBLIC_COLUMNS if column not in header_by_canonical]
    errors.extend(f"Mangler påkrevd kolonne: {column}" for column in missing_columns)

    configured_age_groups = _load_configured_age_groups(config_path)
    rows: list[dict[str, str]] = []
    seen: dict[tuple[str, str, str], int] = {}
    if not missing_columns:
        for index, raw_row in enumerate(reader, start=2):
            row = {column: _normalize_value(raw_row.get(header_by_canonical[column], "")) for column in PUBLIC_COLUMNS}
            for column, value in row.items():
                if not value:
                    errors.append(f"Rad {index}: '{column}' mangler verdi.")
            if configured_age_groups and row["age_group"] and row["age_group"] not in configured_age_groups:
                errors.append(f"Rad {index}: aldersgruppen '{row['age_group']}' finnes ikke i konfigurert age_groups.")
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
        warnings.append("Ignorerte ekstra kolonner som ikke publiseres: " + ", ".join(sorted(excluded_columns, key=str.casefold)))

    report = _base_report(source, raw_headers, included_columns, excluded_columns, warnings, config_path=config_path)
    report.update(
        source_sha256=source_fingerprint,
        row_count=len(rows),
        configured_age_groups=configured_age_groups,
        errors=errors,
        error_count=len(errors),
    )
    if errors:
        raise RegisteredTeamsValidationError(errors, report)

    payload = _build_public_payload(
        rows,
        configured_age_groups=configured_age_groups,
        generated_at=generated_at or _utc_now(),
    )
    return payload, report


def prepare_registered_teams_latest_export(
    *,
    csv_path: str | Path,
    export_dir: str | Path,
    repo_dir: str = ".",
    branch: str = "gh-pages",
    config_path: str | Path | None = None,
    generated_at: str | None = None,
    include_latest_base: bool = True,
    require_latest_base: bool = True,
) -> dict[str, Any]:
    """Prepare a complete Pages snapshot with refreshed registered-team artifacts."""
    export_path = Path(export_dir)
    if export_path.exists():
        shutil.rmtree(export_path)
    export_path.mkdir(parents=True, exist_ok=True)

    base_file_count = 0
    if include_latest_base:
        base_file_count = copy_latest_snapshot(repo_dir=repo_dir, branch=branch, destination_dir=export_path)
        if require_latest_base and base_file_count == 0:
            raise RegisteredTeamsPublishError(
                f"Fant ingen eksisterende /latest/-snapshot på branch '{branch}'. "
                "Avbryter for å unngå å publisere bare Påmeldte lag og slette andre sider."
            )

    registered_team_files = generate_registered_team_artifacts(
        csv_path=csv_path,
        export_dir=export_path,
        config_path=config_path,
        generated_at=generated_at,
    )
    return {
        "export_dir": str(export_path),
        "base_file_count": base_file_count,
        "registered_team_files": registered_team_files,
    }


def generate_registered_team_artifacts(
    *,
    csv_path: str | Path,
    export_dir: str | Path = "export",
    config_path: str | Path | None = None,
    generated_at: str | None = None,
) -> dict[str, str]:
    """Validate *csv_path* and write public/review registered-team artifacts."""
    payload, report = build_registered_teams_payload(csv_path, config_path=config_path, generated_at=generated_at)
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
    """Render a compact, searchable Norwegian club overview."""
    generated_raw = str(payload.get("generated_at", ""))
    generated_at = _format_generated_at(generated_raw)
    total_teams = int(payload.get("total_teams", 0) or 0)

    clubs: dict[str, list[dict[str, str]]] = defaultdict(list)
    for group in payload.get("age_groups", []) or []:
        age_group = str(group.get("age_group", ""))
        for club in group.get("clubs", []) or []:
            club_name = str(club.get("club", ""))
            for team in club.get("teams", []) or []:
                clubs[club_name].append({"age_group": age_group, "label": str(team)})

    def age_sort_key(value: str) -> tuple[int, int | str, str]:
        match = re.fullmatch(r"(J?U)(\d+)", value, flags=re.IGNORECASE)
        return (0, int(match.group(2)), match.group(1).upper()) if match else (1, value.casefold(), value)

    sections: list[str] = []
    for club_name in sorted(clubs, key=str.casefold):
        teams = sorted(clubs[club_name], key=lambda team: (age_sort_key(team["age_group"]), team["label"].casefold()))
        searchable = " ".join([club_name, *[f"{team['age_group']} {team['label']}" for team in teams]]).casefold()
        team_items = "".join(
            '<li>'
            f'<span class="age-badge">{_e(team["age_group"])}</span>'
            f'<span class="team-name">{_e(team["label"])}</span>'
            '</li>'
            for team in teams
        )
        sections.append(
            f'<section class="club" data-search="{_e(searchable)}">'
            '<div class="club-heading">'
            f'<h2>{_e(club_name)}</h2>'
            f'<span>{len(teams)} lag</span>'
            '</div>'
            f'<ul>{team_items}</ul>'
            '</section>'
        )

    if sections:
        content = "\n".join(sections)
        empty_hidden = '<p class="no-results" id="no-results" hidden>Ingen klubber eller lag matcher søket.</p>'
    else:
        content = '<section class="empty-state"><h2>Ingen lag er registrert ennå</h2><p>Oversikten oppdateres når påmeldinger er godkjent.</p></section>'
        empty_hidden = ""

    return f"""<!doctype html>
<html lang="nb">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>Påmeldte lag</title>
<style>
  :root {{ --page:#f5f7fa; --surface:#fff; --ink:#172536; --muted:#64748b; --line:#dbe3ec; --accent:#0d5fa8; --accent-soft:#eaf3fb; --focus:#1d76c5; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--page); color:var(--ink); line-height:1.45; }}
  .wrap {{ width:min(820px,100%); margin:0 auto; padding:clamp(18px,4vw,40px); }}
  header {{ margin-bottom:18px; }}
  .eyebrow {{ margin:0 0 4px; color:var(--accent); font-size:12px; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }}
  h1 {{ margin:0; font-size:clamp(30px,6vw,46px); line-height:1.05; letter-spacing:-.035em; }}
  .intro {{ margin:10px 0 0; max-width:680px; color:var(--muted); font-size:16px; }}
  .updated {{ display:flex; flex-wrap:wrap; gap:5px 14px; align-items:center; margin:14px 0 0; color:var(--muted); font-size:14px; }}
  .updated strong {{ color:var(--ink); }}
  .toolbar {{ position:sticky; top:0; z-index:5; margin:0 0 14px; padding:10px 0; background:linear-gradient(var(--page) 74%,rgba(245,247,250,0)); }}
  .search {{ position:relative; }}
  .search svg {{ position:absolute; left:14px; top:50%; width:20px; height:20px; transform:translateY(-50%); color:var(--muted); pointer-events:none; }}
  .search input {{ width:100%; min-height:46px; padding:11px 46px 11px 44px; border:1px solid #bcc9d6; border-radius:10px; background:var(--surface); color:var(--ink); font:inherit; box-shadow:0 2px 8px rgba(15,23,42,.05); }}
  .search input:focus {{ outline:3px solid rgba(29,118,197,.22); border-color:var(--focus); }}
  .clear {{ position:absolute; right:8px; top:50%; min-width:34px; min-height:34px; transform:translateY(-50%); border:0; border-radius:8px; background:transparent; color:var(--muted); font-size:22px; cursor:pointer; }}
  .clear:hover {{ background:#eef2f6; color:var(--ink); }}
  .results-meta {{ margin:6px 2px 0; color:var(--muted); font-size:13px; }}
  main {{ overflow:hidden; border:1px solid var(--line); border-radius:12px; background:var(--surface); box-shadow:0 6px 18px rgba(15,23,42,.05); }}
  .club {{ padding:16px 18px 17px; }}
  .club + .club {{ border-top:1px solid var(--line); }}
  .club-heading {{ display:flex; justify-content:space-between; gap:14px; align-items:baseline; margin-bottom:8px; }}
  .club h2 {{ margin:0; font-size:20px; letter-spacing:-.015em; }}
  .club-heading span {{ color:var(--muted); font-size:13px; white-space:nowrap; }}
  .club ul {{ display:grid; gap:5px; margin:0; padding:0; list-style:none; }}
  .club li {{ display:grid; grid-template-columns:52px minmax(0,1fr); gap:10px; align-items:baseline; min-height:28px; }}
  .age-badge {{ display:inline-flex; justify-content:center; align-items:center; min-width:44px; padding:3px 7px; border-radius:999px; background:var(--accent-soft); color:#084d87; font-size:12px; font-weight:800; line-height:1.4; }}
  .team-name {{ min-width:0; overflow-wrap:anywhere; }}
  .no-results,.empty-state {{ margin:0; padding:34px 20px; text-align:center; color:var(--muted); }}
  .empty-state h2 {{ margin:0 0 6px; color:var(--ink); font-size:20px; }}
  .empty-state p {{ margin:0; }}
  footer {{ margin-top:16px; color:var(--muted); font-size:13px; }}
  footer a {{ color:var(--accent); }}
  [hidden] {{ display:none!important; }}
  body.is-embed {{ background:transparent; }}
  .is-embed .wrap {{ width:100%; max-width:none; padding:0; }}
  .is-embed header {{ margin:0 0 12px; }}
  .is-embed header > :not(.updated) {{ display:none; }}
  .is-embed .updated {{ margin:0; }}
  .is-embed .toolbar {{ position:static; margin:0 0 12px; padding:0; background:transparent; }}
  .is-embed main {{ box-shadow:none; }}
  .is-embed footer {{ display:none; }}
  @media (max-width:520px) {{
    .wrap {{ padding:18px 12px 28px; }}
    .is-embed .wrap {{ padding:0; }}
    .club {{ padding:14px 13px 15px; }}
    .club-heading {{ align-items:flex-start; }}
    .club li {{ grid-template-columns:48px minmax(0,1fr); gap:8px; }}
  }}
  @media (prefers-reduced-motion:reduce) {{ * {{ scroll-behavior:auto!important; }} }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <p class="eyebrow">RVV Hockey</p>
    <h1>Påmeldte lag</h1>
    <p class="intro">Lag som meldes på via påmeldingsskjemaet, blir publisert her etter automatisk kontroll. Dersom påmeldingen ikke kan behandles automatisk, blir den kontrollert manuelt først.</p>
    <p class="updated"><span><strong>{total_teams}</strong> registrerte lag</span><span>Sist oppdatert: <time datetime="{_e(generated_raw)}">{_e(generated_at)}</time></span></p>
  </header>
  <div class="toolbar">
    <label class="search" for="team-search">
      <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path></svg>
      <input id="team-search" type="search" inputmode="search" autocomplete="off" placeholder="Søk etter klubb, lag eller aldersgruppe" aria-describedby="results-meta">
      <button class="clear" id="clear-search" type="button" aria-label="Tøm søk" hidden>×</button>
    </label>
    <p class="results-meta" id="results-meta" aria-live="polite"></p>
  </div>
  <main id="club-list">{content}{empty_hidden}</main>
  <footer>Oversikten oppdateres automatisk når godkjente påmeldinger behandles. <a href="pameldte-lag.json">Åpne offentlig JSON</a>.</footer>
</div>
<script>
(() => {{
  const HEIGHT_MESSAGE_NAMESPACE = 'rvv.registered-teams';
  const HEIGHT_MESSAGE_TYPE = 'rvv-registered-teams-height';
  const HEIGHT_MESSAGE_SCHEMA_VERSION = 1;
  const DEFAULT_IFRAME_ID = 'rvv-registered-teams-frame';
  const ALLOWED_PARENT_ORIGINS = ['https://www.rvvhockey.no','https://rvvhockey.no'];
  const MIN_EMBED_HEIGHT = 240;
  const MAX_EMBED_HEIGHT = 6000;
  const body = document.body;
  const embedded = window.self !== window.top;
  if (embedded) body.classList.add('is-embed');

  const iframeId = () => new URLSearchParams(window.location.search).get('frame') || DEFAULT_IFRAME_ID;
  const parentTargetOrigin = () => {{
    try {{ const origin = document.referrer ? new URL(document.referrer).origin : ''; if (ALLOWED_PARENT_ORIGINS.includes(origin)) return origin; }} catch (error) {{}}
    try {{ const origin = Array.from(window.location.ancestorOrigins || []).find(item => ALLOWED_PARENT_ORIGINS.includes(item)); if (origin) return origin; }} catch (error) {{}}
    return window.location.origin;
  }};
  const announceHeight = reason => {{
    if (!embedded) return;
    requestAnimationFrame(() => {{
      const height = Math.max(MIN_EMBED_HEIGHT, Math.min(MAX_EMBED_HEIGHT, Math.ceil(Math.max(document.documentElement.scrollHeight, document.body.scrollHeight))));
      window.parent.postMessage({{ type:HEIGHT_MESSAGE_TYPE, namespace:HEIGHT_MESSAGE_NAMESPACE, schema_version:HEIGHT_MESSAGE_SCHEMA_VERSION, iframe_id:iframeId(), height, reason:reason || 'layout', source_path:window.location.pathname }}, parentTargetOrigin());
    }});
  }};

  const input = document.getElementById('team-search');
  const clearButton = document.getElementById('clear-search');
  const clubs = Array.from(document.querySelectorAll('.club'));
  const noResults = document.getElementById('no-results');
  const resultsMeta = document.getElementById('results-meta');
  if (input && clubs.length) {{
    const normalize = value => value.toLocaleLowerCase('nb-NO').trim();
    const render = () => {{
      const query = normalize(input.value);
      let visible = 0;
      clubs.forEach(club => {{ const match = !query || club.dataset.search.includes(query); club.hidden = !match; if (match) visible += 1; }});
      clearButton.hidden = !query;
      if (noResults) noResults.hidden = visible !== 0;
      resultsMeta.textContent = query ? `${{visible}} av ${{clubs.length}} klubber vises` : `${{clubs.length}} klubber`;
      announceHeight('filter');
    }};
    input.addEventListener('input', render);
    clearButton.addEventListener('click', () => {{ input.value=''; input.focus(); render(); }});
    render();
  }} else {{
    announceHeight('initial');
  }}
  if ('ResizeObserver' in window) new ResizeObserver(() => announceHeight('resize-observer')).observe(document.documentElement);
  window.addEventListener('load', () => announceHeight('load'));
  window.addEventListener('resize', () => announceHeight('window-resize'));
}})();
</script>
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
            return (1, int(match.group(2)), match.group(1).upper())
        return (2, age_group.casefold(), age_group)

    age_groups = []
    for age_group in sorted(grouped, key=age_sort_key):
        club_entries = []
        team_count = 0
        for club in sorted(grouped[age_group], key=str.casefold):
            teams = sorted(grouped[age_group][club], key=str.casefold)
            team_count += len(teams)
            club_entries.append({"club": club, "team_count": len(teams), "teams": teams})
        age_groups.append({"age_group": age_group, "team_count": team_count, "club_count": len(club_entries), "clubs": club_entries})

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
        return "ukjent"
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone()
    months = ("januar", "februar", "mars", "april", "mai", "juni", "juli", "august", "september", "oktober", "november", "desember")
    return f"{moment.day}. {months[moment.month - 1]} {moment.year} kl. {moment:%H:%M}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_value(value: object) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "").strip())


def _canonical_header(value: object) -> str:
    return _normalize_value(value).casefold().replace(" ", "_").replace("-", "_")


def _dedupe_key(value: str) -> str:
    return _normalize_value(value).casefold()


def _e(value: object) -> str:
    return html.escape(str(value or ""), quote=True)
