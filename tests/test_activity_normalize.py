from __future__ import annotations

import json

from tournament_scheduler.pipeline.activity_normalize import normalize_activity_json


def test_normalize_activity_json_rewrites_only_date_columns(tmp_path):
    path = tmp_path / "activities.json"
    payload = {
        "schemaVersion": 1,
        "worksheet": "Årshjul",
        "values": [
            ["Måned", "Dato", "Aktivitet", "Sted"],
            ["Desember", "15.12.", "RS U15", "Hall 12.5."],
            ["September", "30.9.", "RS JU16", "Sandefjord"],
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert normalize_activity_json(path, year=2026) is True

    normalized = json.loads(path.read_text(encoding="utf-8"))
    assert normalized["values"][1][1] == "2026-12-15"
    assert normalized["values"][2][1] == "2026-09-30"
    assert normalized["values"][1][3] == "Hall 12.5."


def test_normalize_activity_json_is_idempotent(tmp_path):
    path = tmp_path / "activities.json"
    payload = {
        "schemaVersion": 1,
        "worksheet": "Årshjul",
        "values": [
            ["Dato", "Aktivitet"],
            ["2026-12-15", "RS U15"],
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert normalize_activity_json(path, year=2026) is False
