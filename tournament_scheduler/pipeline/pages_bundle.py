"""Build a sanitized public Pages bundle and privacy report (issue #18).

``pages_publish.publish()`` (issue #17) commits whatever directory it is
given to the ``gh-pages`` branch verbatim — it doesn't know or care what's
in it. This module is the gate in front of that: it turns a raw Stage 4
export directory (which may contain Excel workbooks, Spond exports, and
per-club review packets full of contact info and internal notes) into a
separate, minimal bundle containing only files that are meant to be public,
with any probable secrets, local filesystem paths, or contact info stripped
or blocking publication outright.

Fail-closed defaults:

- Only an explicit allowlist of filenames is ever copied — everything else
  (subdirectories like ``review_packets``, Excel/CSV/Spond exports, unknown
  file types) is excluded by default, not merely "not scanned".
- A probable credential, private key, or bearer-URL/token anywhere in an
  included file blocks the whole bundle (``CapabilityResult.blocked``) —
  the operator must review and either fix the source or explicitly
  acknowledge the finding via ``allow_findings`` before it can be published.
- Local filesystem paths and contact info (emails, phone numbers in a
  labeled context like ``tel:``/``Tlf``) are redacted rather than blocking,
  since they're common accidental inclusions rather than a leak severe
  enough to halt publication, but every redaction is recorded in the
  privacy report.

See ``pipeline/pages_publish.py`` for what happens to the bundle this
produces, and ``docs/ai-operator-roadmap.md`` for the product rationale.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .capability_result import CapabilityResult

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

# The only files copied into the public bundle unless the caller extends
# this via `allowed_filenames`. Deliberately excludes anything with roster,
# contact, or organizer data (Excel/CSV/Spond exports, review_packets/).
DEFAULT_ALLOWED_FILENAMES: frozenset[str] = frozenset(
    {
        "season_plan.html",
        "season_plan_report.html",
        "calendars.html",
        "season_plan.ics",
        "index.html",
    }
)

# File types eligible for inclusion at all, even if the filename is
# allowlisted — an unknown extension fails closed rather than being copied
# on trust.
_ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {".html", ".htm", ".css", ".js", ".ics", ".png", ".jpg", ".jpeg", ".svg", ".ico"}
)

_TEXT_EXTENSIONS: frozenset[str] = frozenset({".html", ".htm", ".css", ".js", ".ics"})

_PRIVACY_REPORT_FILENAME = "pages_privacy_report.json"

# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

_SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "generic_secret_assignment",
        re.compile(
            r"(?i)\b(api[_-]?key|secret|password|passwd|token|auth)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-.]{12,}['\"]?"
        ),
    ),
    ("bearer_header", re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{10,}")),
    (
        "bearer_url",
        re.compile(r"(?i)[?&](access_token|api_key|token|auth)=[^&\s\"'<>]{6,}"),
    ),
]

_LOCAL_PATH_PATTERN = re.compile(
    r"(/Users/[^\s\"'<>]+|/home/[^\s\"'<>]+|[A-Za-z]:\\\\?Users\\\\?[^\s\"'<>]+)"
)
_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Phone numbers are only treated as contact info in a labeled context
# (tel: link, or a "Tlf"/"Tel"/"Phone" label) — an unqualified run of
# digits is far too likely to be a date, id, or score to redact on sight.
_PHONE_PATTERN = re.compile(
    r"(?i)(tel:|\b(tlf|tel|phone)[:\s]*)\+?[0-9][0-9\s\-()]{5,}[0-9]"
)
_ROOT_ABSOLUTE_LINK_PATTERN = re.compile(r"((?:href|src)=[\"'])/(?!/)([^\"']*)")

_REDACTED = "[redacted]"


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@dataclass
class PrivacyReport:
    included_files: list[str] = field(default_factory=list)
    excluded_files: list[dict[str, str]] = field(default_factory=list)
    redactions: list[dict[str, Any]] = field(default_factory=list)
    blocking_findings: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "included_files": list(self.included_files),
            "excluded_files": list(self.excluded_files),
            "redactions": list(self.redactions),
            "blocking_findings": list(self.blocking_findings),
        }

    def write(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def _rewrite_root_absolute_links(text: str) -> str:
    """Rewrite ``href="/x"``/``src="/x"`` to a relative ``"x"``.

    A root-absolute link resolves against the site root, which breaks when
    the bundle is served from a GitHub Pages project subpath
    (``/<repo>/latest/`` or ``/<repo>/runs/<run-id>/``) instead of the
    domain root. Protocol-relative (``//host/...``) and normal
    ``http(s)://`` links are left untouched.
    """
    return _ROOT_ABSOLUTE_LINK_PATTERN.sub(lambda m: f"{m.group(1)}{m.group(2)}", text)


def _find_secrets(text: str, allow_findings: frozenset[str]) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    for name, pattern in _SECRET_PATTERNS:
        for match in pattern.finditer(text):
            matched_text = match.group(0)
            if any(allowed and allowed in matched_text for allowed in allow_findings):
                continue
            findings.append((name, matched_text))
    return findings


def _redact_contact_and_paths(text: str) -> tuple[str, list[tuple[str, int]]]:
    counts: list[tuple[str, int]] = []
    for category, pattern in (
        ("local_path", _LOCAL_PATH_PATTERN),
        ("contact_email", _EMAIL_PATTERN),
        ("contact_phone", _PHONE_PATTERN),
    ):
        text, n = pattern.subn(_REDACTED, text)
        if n:
            counts.append((category, n))
    return text, counts


def build_public_bundle(
    export_dir: str,
    output_dir: str,
    *,
    allowed_filenames: frozenset[str] | set[str] | None = None,
    allow_findings: frozenset[str] | set[str] | None = None,
) -> CapabilityResult:
    """Build a sanitized public bundle from *export_dir* into *output_dir*.

    Only top-level files in *export_dir* whose name is in
    *allowed_filenames* (default :data:`DEFAULT_ALLOWED_FILENAMES`) and
    whose extension is a known static-asset type are copied; everything
    else (including subdirectories such as ``review_packets/``) is
    excluded and recorded in the privacy report, not silently skipped.

    *allow_findings* is a set of literal substrings that, when they appear
    inside an otherwise-blocking secret match, mark that specific match as
    an acknowledged false positive instead of a blocker — for a human who
    has reviewed a flagged string and confirmed it isn't actually
    sensitive (e.g. a placeholder value in a fixture).

    Returns a :class:`CapabilityResult`:

    - ``blocked`` (``requires_human=True``) if any probable secret was
      found — *output_dir* is not left in a publishable state.
    - ``ok`` otherwise, with the bundle written to *output_dir* and the
      privacy report path in ``artifacts``.

    Never raises for anything past basic argument validation.
    """
    export_path = Path(export_dir)
    if not export_path.is_dir():
        return CapabilityResult.failed(
            f"Eksportmappe '{export_dir}' finnes ikke.", capability="pages_bundle"
        )

    names = frozenset(allowed_filenames) if allowed_filenames is not None else DEFAULT_ALLOWED_FILENAMES
    overrides = frozenset(allow_findings) if allow_findings is not None else frozenset()

    output_path = Path(output_dir)
    if output_path.exists():
        shutil.rmtree(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    report = PrivacyReport()

    for entry in sorted(export_path.iterdir()):
        if entry.is_dir():
            report.excluded_files.append(
                {"file": entry.name, "reason": "directories are not published by default"}
            )
            continue

        if entry.name not in names:
            report.excluded_files.append(
                {"file": entry.name, "reason": "not in the public filename allowlist"}
            )
            continue

        if entry.suffix.lower() not in _ALLOWED_EXTENSIONS:
            report.excluded_files.append(
                {"file": entry.name, "reason": f"unknown/unapproved file type '{entry.suffix}'"}
            )
            continue

        if entry.suffix.lower() not in _TEXT_EXTENSIONS:
            # Known static asset type (image, icon) but not text — copy
            # as-is; there is no meaningful way to pattern-scan it here.
            shutil.copyfile(entry, output_path / entry.name)
            report.included_files.append(entry.name)
            continue

        try:
            text = entry.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            report.excluded_files.append(
                {"file": entry.name, "reason": "could not be read as UTF-8 text"}
            )
            continue

        secrets = _find_secrets(text, overrides)
        if secrets:
            for category, matched_text in secrets:
                report.blocking_findings.append(
                    {"file": entry.name, "category": category, "detail": matched_text}
                )
            continue

        text, redaction_counts = _redact_contact_and_paths(text)
        text = _rewrite_root_absolute_links(text)
        for category, count in redaction_counts:
            report.redactions.append({"file": entry.name, "category": category, "count": count})

        (output_path / entry.name).write_text(text, encoding="utf-8")
        report.included_files.append(entry.name)

    report_path = output_path.parent / _PRIVACY_REPORT_FILENAME
    report.write(report_path)

    if report.blocking_findings:
        shutil.rmtree(output_path, ignore_errors=True)
        finding_summary = ", ".join(
            f"{f['file']}:{f['category']}" for f in report.blocking_findings
        )
        return CapabilityResult.blocked(
            f"Publisering blokkert — mulige hemmeligheter funnet: {finding_summary}",
            capability="pages_bundle",
            problems=[f"{f['file']}: {f['category']}" for f in report.blocking_findings],
            artifacts=[str(report_path)],
        )

    return CapabilityResult.ok(
        f"{len(report.included_files)} fil(er) godkjent for offentlig publisering, "
        f"{len(report.excluded_files)} ekskludert, {len(report.redactions)} redigering(er)",
        capability="pages_bundle",
        evidence=[
            f"included={len(report.included_files)}",
            f"excluded={len(report.excluded_files)}",
            f"redactions={len(report.redactions)}",
        ],
        artifacts=[str(output_path), str(report_path)],
    )
