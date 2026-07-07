"""Deterministic fingerprint helpers for pipeline inputs and checkpoints."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_FINGERPRINT_KEYS = {"input_fingerprint", "effective_config_fingerprint"}


def file_sha256(path: str | Path) -> str:
    """Return the SHA-256 hex digest of *path* read as bytes."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_payload_sha256(payload: Any) -> str:
    """Return a deterministic SHA-256 digest for a JSON-serialisable payload."""
    encoded = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def without_fingerprint_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Return *payload* without top-level fingerprint metadata keys."""
    return {key: value for key, value in payload.items() if key not in _FINGERPRINT_KEYS}


def build_stage1_fingerprints(
    input_path: str | Path,
    raw_config: dict[str, Any],
    computed_config: dict[str, Any],
) -> dict[str, dict[str, str]]:
    """Build Stage 1 workbook and effective-config fingerprint metadata.

    ``input_fingerprint`` tracks the exact workbook bytes. The
    ``effective_config_fingerprint`` tracks the logical config consumed by
    downstream stages: the parsed workbook fields plus Stage 1's computed
    checkpoint fields, excluding fingerprint metadata itself.
    """
    resolved = Path(input_path).resolve()
    effective_payload = {
        "raw_config": raw_config,
        "computed_config": without_fingerprint_metadata(computed_config),
    }
    return {
        "input_fingerprint": {
            "algorithm": "sha256",
            "path": str(resolved),
            "sha256": file_sha256(resolved),
        },
        "effective_config_fingerprint": {
            "algorithm": "sha256",
            "sha256": stable_payload_sha256(effective_payload),
        },
    }
