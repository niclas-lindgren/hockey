"""Tests for tournament_scheduler.pipeline.llm_scraper.

Covers:
  - LLMAction / action_from_dict parsing (including edge cases)
  - _extract_json_from_llm (markdown fences, embedded JSON, noise)
  - _execute_action (mapped to mocked Playwright calls)
  - _action_events_to_calendar_events / _events_to_action_dicts (round-trip)
  - _build_system_prompt and _build_user_message
  - LLMGuidedScraper.run() with mocked Playwright and LLM
  - Max iterations exceeded blocking behavior
  - Non-Playwright sources bypassing the agent
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest

from tournament_scheduler.models import CalendarEvent
from tournament_scheduler.pipeline.llm_scraper import (
    LLMAction,
    LLMGuidedScraper,
    _action_events_to_calendar_events,
    _build_system_prompt,
    _build_user_message,
    _events_to_action_dicts,
    _execute_action,
    _extract_json_from_llm,
    action_from_dict,
    capture_dom_snapshot,
)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def mock_page():
    """Return a MagicMock that behaves like a Playwright Page."""
    page = MagicMock()
    page.title.return_value = "Test Calendar"
    page.url = "https://example.com/calendar"
    page.viewport_size = {"width": 1920, "height": 1080}
    page.content.return_value = "<html><body><p>Hello</p></body></html>"

    # Mock locators
    def mock_locator(selector: str):
        loc = MagicMock()
        loc.count.return_value = 0

        if "button" in selector or "role='button'" in selector:
            btn = MagicMock()
            btn.inner_text.return_value = "Vis kalender"
            btn.get_attribute.return_value = "btn-calendar"
            loc.count.return_value = 1
            loc.nth.return_value = btn
        return loc

    page.locator.side_effect = mock_locator
    return page


@pytest.fixture
def mock_playwright(mock_page):
    """Return a context manager that yields a mocked Playwright."""
    playwright_cls = MagicMock()
    browser = MagicMock()
    context = MagicMock()
    page = mock_page

    browser.new_page.return_value = page
    context.new_page.return_value = page
    playwright_cls.chromium.launch.return_value = browser

    # sync_playwright is a function, not a class — mock the module
    with patch("playwright.sync_api.sync_playwright") as mock_sp:
        mock_sp.return_value.__enter__.return_value = playwright_cls
        yield mock_sp


# ===========================================================================
# Action schema tests
# ===========================================================================


class TestActionFromDict:
    def test_click_action(self):
        action = action_from_dict({
            "action": "click",
            "selector": "button:text('Vis kalender')",
        })
        assert action.action == "click"
        assert action.selector == "button:text('Vis kalender')"

    def test_done_action_with_events(self):
        action = action_from_dict({
            "action": "done",
            "events": [
                {"date": "15.01.2026", "name": "Trening", "duration_hours": 2.0},
            ],
        })
        assert action.action == "done"
        assert len(action.events) == 1
        assert action.events[0]["name"] == "Trening"

    def test_select_action(self):
        action = action_from_dict({
            "action": "select",
            "selector": "select#month",
            "value": "2026-01",
        })
        assert action.action == "select"
        assert action.value == "2026-01"

    def test_type_action(self):
        action = action_from_dict({
            "action": "type",
            "selector": "input[type='date']",
            "value": "2026-01-15",
        })
        assert action.action == "type"

    def test_wait_action(self):
        action = action_from_dict({"action": "wait", "ms": 2000})
        assert action.action == "wait"
        assert action.ms == 2000

    def test_scroll_action(self):
        action = action_from_dict({
            "action": "scroll", "direction": "down", "amount": 300,
        })
        assert action.action == "scroll"
        assert action.direction == "down"
        assert action.amount == 300

    def test_extract_action(self):
        action = action_from_dict({"action": "extract"})
        assert action.action == "extract"

    def test_camel_case_fallback(self):
        """camelCase keys are accepted as well."""
        action = action_from_dict({
            "action": "click",
            "css": "button.primary",
            "reason": "Found calendar button",
        })
        assert action.action == "click"
        assert action.selector == "button.primary"
        assert action.reasoning == "Found calendar button"

    def test_wait_ms_fallback(self):
        action = action_from_dict({"action": "wait", "wait_ms": 3000})
        assert action.ms == 3000

    def test_reason_fallback(self):
        action = action_from_dict({"action": "wait", "reason": "Loading..."})
        assert action.reasoning == "Loading..."

    def test_invalid_action_raises(self):
        with pytest.raises(ValueError, match="Ugyldig"):
            action_from_dict({"action": "fly"})

    def test_missing_action_raises(self):
        with pytest.raises(ValueError):
            action_from_dict({"selector": "#btn"})

    def test_empty_action_raises(self):
        with pytest.raises(ValueError):
            action_from_dict({"action": ""})


# ===========================================================================
# JSON extraction tests
# ===========================================================================


class TestExtractJsonFromLlm:
    def test_bare_json(self):
        result = _extract_json_from_llm('{"action": "click"}')
        assert json.loads(result) == {"action": "click"}

    def test_markdown_json_fence(self):
        result = _extract_json_from_llm("```json\n{\"action\": \"click\"}\n```")
        assert json.loads(result) == {"action": "click"}

    def test_markdown_fence_no_lang(self):
        result = _extract_json_from_llm("```\n{\"action\": \"done\"}\n```")
        assert json.loads(result) == {"action": "done"}

    def test_embedded_in_prose(self):
        result = _extract_json_from_llm(
            "I will click the button. {\"action\": \"click\"} Let's see what happens."
        )
        assert json.loads(result) == {"action": "click"}

    def test_no_json_found(self):
        """Should return the stripped text even if not valid JSON."""
        result = _extract_json_from_llm("Nothing here")
        assert result == "Nothing here"

    def test_multiple_braces_cannot_parse(self):
        """Multiple JSON objects result in invalid JSON — function returns as-is."""
        result = _extract_json_from_llm(
            'text {"action": "click"} trailing {"other": "data"}'
        )
        # The function takes first { to last } which makes invalid JSON
        with pytest.raises(json.JSONDecodeError):
            json.loads(result)

    def test_trailing_newlines(self):
        result = _extract_json_from_llm('{"action": "done"}\n\n')
        assert json.loads(result) == {"action": "done"}


# ===========================================================================
# Action execution tests (mocked Playwright)
# ===========================================================================


class TestExecuteAction:
    def test_click_valid_selector(self):
        page = MagicMock()
        element = MagicMock()
        element.count.return_value = 1
        page.locator.return_value = element

        action = LLMAction(action="click", selector="#btn")
        result = _execute_action(action, page)
        assert result is True
        element.first.click.assert_called_once()

    def test_click_missing_selector(self):
        action = LLMAction(action="click", selector="")
        result = _execute_action(action, MagicMock())
        assert result is False

    def test_click_element_not_found(self):
        page = MagicMock()
        element = MagicMock()
        element.count.return_value = 0
        page.locator.return_value = element

        action = LLMAction(action="click", selector="#missing")
        result = _execute_action(action, page)
        assert result is False

    def test_select_valid(self):
        page = MagicMock()
        element = MagicMock()
        element.count.return_value = 1
        page.locator.return_value = element

        action = LLMAction(action="select", selector="select#m", value="opt1")
        result = _execute_action(action, page)
        assert result is True
        element.first.select_option.assert_called_once_with("opt1")

    def test_type_valid(self):
        page = MagicMock()
        element = MagicMock()
        element.count.return_value = 1
        page.locator.return_value = element

        action = LLMAction(action="type", selector="input#name", value="test")
        result = _execute_action(action, page)
        assert result is True
        element.first.fill.assert_called_once_with("test")

    def test_wait(self, monkeypatch):
        import time as time_module

        original_sleep = time_module.sleep
        slept: list[float] = []

        def mock_sleep(seconds: float):
            slept.append(seconds)

        monkeypatch.setattr(time_module, "sleep", mock_sleep)

        action = LLMAction(action="wait", ms=1000)
        result = _execute_action(action, MagicMock())
        assert result is True
        assert any(0.9 <= s <= 1.1 for s in slept), f"Expected ~1s sleep, got {slept}"

    def test_wait_minimum_100ms(self, monkeypatch):
        import time as time_module

        slept: list[float] = []

        def mock_sleep(seconds: float):
            slept.append(seconds)

        monkeypatch.setattr(time_module, "sleep", mock_sleep)

        action = LLMAction(action="wait", ms=10)
        result = _execute_action(action, MagicMock())
        assert result is True
        # Should have been clamped to 100ms minimum
        assert any(0.09 <= s <= 0.12 for s in slept)

    def test_scroll_down(self):
        page = MagicMock()
        action = LLMAction(action="scroll", direction="down", amount=300)
        result = _execute_action(action, page)
        assert result is True
        page.evaluate.assert_called_once_with("window.scrollBy(0, 300)")

    def test_scroll_up(self):
        page = MagicMock()
        action = LLMAction(action="scroll", direction="up", amount=200)
        result = _execute_action(action, page)
        assert result is True
        page.evaluate.assert_called_once_with("window.scrollBy(0, -200)")

    def test_extract_always_succeeds(self):
        action = LLMAction(action="extract")
        result = _execute_action(action, MagicMock())
        assert result is True

    def test_done_always_succeeds(self):
        action = LLMAction(action="done")
        result = _execute_action(action, MagicMock())
        assert result is True

    def test_unknown_action(self):
        action = LLMAction(action="click")  # Valid, but try unknown
        action.action = "fly"  # type: ignore[assignment]
        result = _execute_action(action, MagicMock())
        assert result is False

    def test_exception_during_action(self):
        page = MagicMock()
        page.locator.side_effect = Exception("Browser crashed")
        action = LLMAction(action="click", selector="#btn")
        result = _execute_action(action, page)
        assert result is False


# ===========================================================================
# Event conversion tests
# ===========================================================================


class TestEventConversion:
    def test_action_events_to_calendar_events(self):
        dicts = [
            {"date": "15.01.2026", "name": "Training", "duration_hours": 2.0},
            {"date": "16.01.2026", "name": "Match", "duration_hours": 1.5},
        ]
        events = _action_events_to_calendar_events(dicts)
        assert len(events) == 2
        assert events[0].name == "Training"
        assert events[0].date == "15.01.2026"
        assert events[0].duration_hours == 2.0
        assert events[1].name == "Match"

    def test_action_events_empty(self):
        assert _action_events_to_calendar_events([]) == []

    def test_action_events_skips_invalid(self):
        dicts = [
            {"date": "15.01.2026", "name": "Valid", "duration_hours": 1.0},
            {"date": "", "name": "Missing date"},
            {"name": "Missing date field"},
            {"date": "not-a-date", "name": "Bad date"},
            None,
        ]
        events = _action_events_to_calendar_events(dicts)
        assert len(events) == 1
        assert events[0].name == "Valid"

    def test_action_events_iso_date_fallback(self):
        dicts = [
            {"date": "2026-01-15", "name": "ISO format", "duration_hours": 1.0},
        ]
        events = _action_events_to_calendar_events(dicts)
        assert len(events) == 1
        assert events[0].date == "15.01.2026"

    def test_events_to_action_dicts(self):
        events = [
            CalendarEvent(
                date="15.01.2026",
                name="Booking",
                datetime=datetime(2026, 1, 15, 10, 0),
                duration_hours=2.0,
            ),
        ]
        dicts = _events_to_action_dicts(events)
        assert len(dicts) == 1
        assert dicts[0]["name"] == "Booking"
        assert dicts[0]["duration_hours"] == 2.0
        assert "datetime" in dicts[0]

    def test_events_to_action_dicts_empty(self):
        assert _events_to_action_dicts([]) == []


# ===========================================================================
# Prompt building tests
# ===========================================================================


class TestPromptBuilding:
    def test_system_prompt_contains_key_elements(self):
        prompt = _build_system_prompt(
            "TestSource",
            datetime(2026, 1, 1),
            datetime(2026, 3, 31),
        )
        assert "TestSource" in prompt
        assert "01.01.2026" in prompt
        assert "31.03.2026" in prompt
        assert "click" in prompt
        assert "done" in prompt
        assert "select" in prompt
        assert "JSON" in prompt
        assert len(prompt) > 500

    def test_user_message_contains_snapshot(self):
        snapshot = {
            "title": "Test Page",
            "url": "https://example.com",
            "viewport_width": 1920,
            "viewport_height": 1080,
            "visible_text": "Hello world calendar data",
            "interactive_elements": [
                {"tag": "button", "role": "button", "text": "Click me", "selector": "#btn1"},
                {"tag": "a", "role": "link", "text": "Kalender", "selector": "a.kalender"},
            ],
            "element_count": 2,
        }
        msg = _build_user_message(
            snapshot, "TestSource",
            datetime(2026, 1, 1), datetime(2026, 3, 31),
            1, 20,
        )
        assert "Test Page" in msg
        assert "Click me" in msg
        assert "Kalender" in msg
        assert "1/20" in msg
        assert "1920x1080" in msg or "1920" in msg


# ===========================================================================
# LLMGuidedScraper integration tests (mocked Playwright + mocked LLM)
# ===========================================================================


class TestLLMGuidedScraper:
    def test_immediate_done_returns_events(self, mock_playwright):
        """Scenario 1: LLM immediately finds events and returns done."""
        mock_client = MagicMock()
        mock_client.complete.return_value = MagicMock(
            text=json.dumps({
                "action": "done",
                "events": [
                    {"date": "15.01.2026", "name": "Trening", "duration_hours": 2.0},
                    {"date": "16.01.2026", "name": "Kamp", "duration_hours": 1.5},
                ],
            })
        )

        scraper = LLMGuidedScraper(client=mock_client, max_iterations=5)
        events = scraper.run(
            url="https://example.com/calendar",
            name="Test",
            start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 3, 31),
        )

        assert len(events) == 2
        assert events[0].name == "Trening"
        assert events[1].name == "Kamp"
        # Only one LLM call should be made (immediate done)
        assert mock_client.complete.call_count == 1

    def test_click_then_done(self, mock_playwright, mock_page):
        """Scenario 2: LLM needs a click action before finding events."""
        responses = [
            MagicMock(text=json.dumps({
                "action": "click",
                "selector": "button:text('Vis kalender')",
            })),
            MagicMock(text=json.dumps({
                "action": "done",
                "events": [
                    {"date": "15.01.2026", "name": "Etter klikk", "duration_hours": 1.0},
                ],
            })),
        ]

        mock_client = MagicMock()
        mock_client.complete.side_effect = responses

        scraper = LLMGuidedScraper(client=mock_client, max_iterations=5)
        events = scraper.run(
            url="https://example.com/calendar",
            name="Test",
            start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 3, 31),
        )

        assert len(events) == 1
        assert events[0].name == "Etter klikk"
        assert mock_client.complete.call_count == 2
        # Verify the click action was executed
        assert mock_page.locator.called

    def test_select_then_done(self, mock_playwright, mock_page):
        """Scenario 3: LLM needs a select action before finding events."""
        responses = [
            MagicMock(text=json.dumps({
                "action": "select",
                "selector": "select#month",
                "value": "2026-01",
            })),
            MagicMock(text=json.dumps({
                "action": "done",
                "events": [
                    {"date": "20.01.2026", "name": "Etter valg", "duration_hours": 2.0},
                ],
            })),
        ]

        mock_client = MagicMock()
        mock_client.complete.side_effect = responses

        # Make the select locator return something clickable
        elem = MagicMock()
        elem.count.return_value = 1
        mock_page.locator.return_value = elem

        scraper = LLMGuidedScraper(client=mock_client, max_iterations=5)
        events = scraper.run(
            url="https://example.com/calendar",
            name="Test",
            start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 3, 31),
        )

        assert len(events) == 1
        assert events[0].name == "Etter valg"
        assert mock_client.complete.call_count == 2

    def test_max_iterations_exceeded_returns_empty(self, mock_playwright):
        """Scenario 4: Max iterations exceeded — blocking behavior."""
        mock_client = MagicMock()
        mock_client.complete.return_value = MagicMock(
            text=json.dumps({"action": "wait", "ms": 100})
        )

        scraper = LLMGuidedScraper(client=mock_client, max_iterations=3)
        events = scraper.run(
            url="https://example.com/calendar",
            name="Test",
            start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 3, 31),
        )

        assert len(events) == 0  # Empty = blocked
        # Should have called LLM exactly max_iterations times
        assert mock_client.complete.call_count == 3

    def test_invalid_json_response_continues(self, mock_playwright):
        """Invalid LLM JSON should not crash — scraper continues."""
        responses = [
            MagicMock(text="This is not JSON"),
            MagicMock(text="```\n{\"action\": \"done\", \"events\": []}\n```"),
        ]
        mock_client = MagicMock()
        mock_client.complete.side_effect = responses

        scraper = LLMGuidedScraper(client=mock_client, max_iterations=5)
        events = scraper.run(
            url="https://example.com/calendar",
            name="Test",
            start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 3, 31),
        )

        # Should not crash, should return empty since done had no events
        assert isinstance(events, list)
        assert mock_client.complete.call_count == 2

    def test_llm_unavailable_error(self):
        """Without LLM client, scraper raises RuntimeError."""
        with patch("tournament_scheduler.pipeline.llm_scraper._LLM_AVAILABLE", False):
            scraper = LLMGuidedScraper(client=MagicMock(), max_iterations=3)
            with pytest.raises(RuntimeError, match="ikke tilgjengelig"):
                scraper.run(
                    url="https://example.com",
                    name="Test",
                    start_date=datetime(2026, 1, 1),
                    end_date=datetime(2026, 3, 31),
                )


# ===========================================================================
# Edge case tests
# ===========================================================================


class TestEdgeCases:
    def test_dom_snapshot_with_empty_page(self):
        """Empty/minimal page should not crash the snapshotter."""
        page = MagicMock()
        page.title.return_value = ""
        page.url = ""
        page.viewport_size = None
        page.content.return_value = ""

        # All locators return zero elements
        loc = MagicMock()
        loc.count.return_value = 0
        page.locator.return_value = loc

        snapshot = capture_dom_snapshot(page)
        assert snapshot["title"] == ""
        assert snapshot["url"] == ""
        assert snapshot["element_count"] == 0

    def test_execute_action_with_exception(self):
        """Exceptions during action execution return False, don't crash."""
        page = MagicMock()
        page.locator.side_effect = Exception("fail")
        action = LLMAction(action="click", selector="#btn")
        result = _execute_action(action, page)
        assert result is False

    def test_scroll_no_direction_defaults_down(self):
        page = MagicMock()
        action = LLMAction(action="scroll", amount=200)
        result = _execute_action(action, page)
        assert result is True
        page.evaluate.assert_called_once()

    def test_type_with_no_selector(self):
        action = LLMAction(action="type", value="test")
        result = _execute_action(action, MagicMock())
        assert result is False

    def test_select_with_no_value(self):
        page = MagicMock()
        element = MagicMock()
        element.count.return_value = 1
        page.locator.return_value = element

        action = LLMAction(action="select", selector="#m")
        result = _execute_action(action, page)
        assert result is False
