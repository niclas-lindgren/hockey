from __future__ import annotations

from datetime import datetime, timedelta

from tournament_scheduler.pipeline.scraper_sportello import _run_sportello_scraper


class _FakeResponse:
    def __init__(self, payload: dict[str, object]):
        self._payload = payload
        import json

        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self) -> dict[str, object]:
        return self._payload

    def raise_for_status(self) -> None:
        return None


class _FakeSession:
    def __init__(self, responses: list[dict[str, object]]):
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def post(self, url, json=None, headers=None, timeout=None):  # noqa: A002
        self.calls.append((json or {}).get("variables", {}).get("filter", {}))
        index = len(self.calls) - 1
        payload = self.responses[index] if index < len(self.responses) else {"data": {"publicBookings": []}}
        return _FakeResponse(payload)


def test_run_sportello_scraper_chunks_windows_and_normalizes_times() -> None:
    start = datetime(2026, 9, 1)
    end = datetime(2026, 12, 15)
    booking = {
        "id": 1,
        "displayName": "Holmen U10 trening",
        "startTime": "2026-09-03T08:00:00Z",
        "endTime": "2026-09-03T09:30:00Z",
        "allDay": False,
        "team": {"displayName": "Holmen U10"},
        "location": {"displayName": "Holmen Ishall"},
        "activityType": {"displayName": "Trening", "typeValue": "TRAINING"},
        "teamText": "Holmen U10",
        "awayTeamText": "",
    }
    session = _FakeSession([
        {"data": {"publicBookings": [booking, booking]}},
        {"data": {"publicBookings": []}},
    ])

    events, raw = _run_sportello_scraper(
        "https://kalender.sportello.no/booking/11055",
        "Holmen",
        start,
        end,
        session=session,
    )

    assert len(session.calls) == 2
    for filter_payload in session.calls:
        span = datetime.fromisoformat(str(filter_payload["endTime"]).replace("Z", "+00:00")) - datetime.fromisoformat(str(filter_payload["startTime"]).replace("Z", "+00:00"))
        assert span <= timedelta(days=91)

    assert len(events) == 1
    event = events[0]
    assert event.date == "03.09.2026"
    assert event.datetime.hour == 10
    assert event.datetime.minute == 0
    assert event.duration_hours == 1.5
    assert event.location == "Holmen Ishall"
    assert "\"club_id\": 11055" in raw
