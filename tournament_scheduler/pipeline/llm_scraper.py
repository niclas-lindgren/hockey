"""LLM-guided browser scraper for JS-rendered calendar SPAs.

Provides:
  - ``LLMAction`` / ``LLMActionType`` — typed action schema for the LLM's
    structured response (click, select, type, wait, scroll, extract, done).
  - ``parse_action`` — deserialise the LLM's JSON response into an action.
  - ``capture_dom_snapshot`` — build a simplified text representation of a
    Playwright page (strips ``<script>`` and ``<style>`` tags, extracts
    interactive elements, viewport, and readable text).
  - ``LLMGuidedScraper`` — the agent loop that iterates: capture snapshot →
    send to LLM → execute returned action → repeat until events are found
    or the iteration limit is hit.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Literal

from ..models import CalendarEvent

logger = logging.getLogger(__name__)

# ===========================================================================
# Action schema — structured action the LLM can return
# ===========================================================================

# Valid action type literals matching what the LLM will output.
# Each corresponds to a specific Playwright operation the agent loop can
# perform on the browser page.
LLMActionType = Literal[
    "click",
    "select",
    "type",
    "wait",
    "scroll",
    "extract",
    "done",
]


@dataclass
class LLMAction:
    """A structured action returned by the LLM to guide browser interaction.

    Attributes
    ----------
    action:
        One of ``click``, ``select``, ``type``, ``wait``, ``scroll``,
        ``extract``, or ``done``.
    selector:
        Playwright-compatible CSS / text selector (required for ``click``,
        ``select``, ``type``; optional for others).
    value:
        Value to use for ``select`` (option value) or ``type`` (text to type).
    direction:
        Scroll direction — ``"up"`` or ``"down"`` (only for ``scroll``).
    amount:
        Scroll pixel amount (only for ``scroll``).
    ms:
        Milliseconds to wait (only for ``wait``).
    events:
        Extracted calendar events (only for ``done`` action type).
    reasoning:
        Optional free-text explanation from the LLM for this action.
    """

    action: LLMActionType
    selector: str = ""
    value: str = ""
    direction: str = ""
    amount: int = 0
    ms: int = 500
    events: list[dict[str, Any]] = field(default_factory=list)
    reasoning: str = ""


def action_from_dict(data: dict[str, Any]) -> LLMAction:
    """Deserialise an ``LLMAction`` from a raw dict (LLM JSON response).

    Accepts keys in both snake_case and camelCase to tolerate LLM output
    variations. Unknown keys are silently ignored.

    Raises ``ValueError`` if the ``action`` field is missing or not a
    recognised action type.
    """
    raw_action = data.get("action", "")
    if not raw_action or raw_action not in _VALID_ACTIONS:
        raise ValueError(
            f"Ugyldig eller manglende action-type: '{raw_action}'. "
            f"Forventet en av: {', '.join(sorted(_VALID_ACTIONS))}"
        )

    return LLMAction(
        action=raw_action,  # type: ignore[arg-type]
        selector=data.get("selector", data.get("css", "")),
        value=data.get("value", ""),
        direction=data.get("direction", ""),
        amount=int(data.get("amount", 0)),
        ms=int(data.get("ms", data.get("wait_ms", 500))),
        events=data.get("events", []),
        reasoning=data.get("reasoning", data.get("reason", "")),
    )


_VALID_ACTIONS: set[str] = {
    "click", "select", "type", "wait", "scroll", "extract", "done",
}


# ===========================================================================
# DOM snapshot — simplified text representation of a Playwright page
# ===========================================================================

MAX_VISIBLE_TEXT_CHARS = 8_000
MAX_INTERACTIVE_ELEMENTS = 50


def capture_dom_snapshot(page: Any) -> dict[str, Any]:
    """Capture a simplified text representation of a Playwright page.

    The snapshot is designed to be sent to an LLM for interaction decisions.
    It strips ``<script>`` and ``<style>`` tags, extracts interactive elements
    (buttons, links, inputs, selects), and includes the page's readable text
    truncated to ~8000 characters.

    Parameters
    ----------
    page:
        A Playwright ``Page`` instance (sync API).

    Returns
    -------
    dict
        Snapshot with keys:
        - ``title`` — document title
        - ``url`` — current page URL
        - ``viewport_width`` / ``viewport_height`` — current viewport dimensions
        - ``visible_text`` — page text content (ta  trunccapped to 8000 chars)
        - ``interactive_elements`` — list of {tag, role, text, selector} dicts
        - ``element_count`` — total number of interactive elements found
    """
    try:
        title = page.title()
    except Exception:
        title = ""

    try:
        current_url = page.url
    except Exception:
        current_url = ""

    try:
        vp = page.viewport_size
        vp_width = vp.get("width", 0) if vp else 0
        vp_height = vp.get("height", 0) if vp else 0
    except Exception:
        vp_width = 0
        vp_height = 0

    # Get raw HTML and strip <script>/<style> tags
    try:
        raw_html = page.content()
    except Exception:
        raw_html = ""
    cleaned_html = _strip_script_and_style(raw_html)

    # Extract readable visible text
    visible_text = _extract_visible_text(cleaned_html)
    if len(visible_text) > MAX_VISIBLE_TEXT_CHARS:
        visible_text = visible_text[:MAX_VISIBLE_TEXT_CHARS] + "\n... [truncated]"

    # Extract interactive elements using Playwright locators
    interactive_elements = _extract_interactive_elements(page)

    return {
        "title": title,
        "url": current_url,
        "viewport_width": vp_width,
        "viewport_height": vp_height,
        "visible_text": visible_text,
        "interactive_elements": interactive_elements[:MAX_INTERACTIVE_ELEMENTS],
        "element_count": len(interactive_elements),
    }


def _strip_script_and_style(html: str) -> str:
    """Remove ``<script>`` and ``<style>`` tags (and their content) from HTML.

    Uses a regex that handles both ``<script>...</script>``,
    ``<style>...</style>``, and self-closing variants.
    """
    # Remove <script ...>...</script> and <style ...>...</style>
    cleaned = re.sub(
        r'<(script|style)\b[^>]*>.*?</\1\s*>',
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Remove remaining self-closing script/style tags (rare but safe)
    cleaned = re.sub(
        r'<(script|style)\b[^>]*/>',
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned


def _extract_visible_text(html: str) -> str:
    """Extract readable text from cleaned HTML.

    Uses BeautifulSoup when available (preferred — better text extraction),
    otherwise falls back to a basic regex-based tag stripping.
    """
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        # Remove remaining hidden/irrelevant elements
        for tag in soup(["script", "style", "noscript", "meta", "link", "svg"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()
    except ImportError:
        # Fallback: basic tag-stripping regex
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


def _extract_interactive_elements(page: Any) -> list[dict[str, str]]:
    """Find interactive elements on the page and return their descriptors.

    Uses Playwright locators to collect buttons, links, inputs, selects,
    and textareas. Element descriptors include the tag name, ARIA role,
    visible text / label / placeholder, and a Playwright-compatible CSS
    selector that should work for ``page.click()`` / ``page.fill()``.
    """
    elements: list[dict[str, str]] = []

    try:
        # --- Buttons ---
        buttons = page.locator(
            "button, input[type='submit'], input[type='button'], "
            "[role='button']"
        )
        btn_count = buttons.count()
        for i in range(min(btn_count, 30)):
            try:
                tag = "button"
                text = buttons.nth(i).inner_text().strip()[:80]
                if not text:
                    text = buttons.nth(i).get_attribute("aria-label") or ""
                if not text:
                    text = buttons.nth(i).get_attribute("title") or ""
                sel = _build_selector_for(buttons.nth(i))
                elements.append({
                    "tag": tag,
                    "role": "button",
                    "text": text[:60],
                    "selector": sel,
                })
            except Exception:
                continue
    except Exception:
        pass

    try:
        # --- Links ---
        links = page.locator("a[href]")
        link_count = links.count()
        for i in range(min(link_count, 20)):
            try:
                tag = "a"
                text = links.nth(i).inner_text().strip()[:80]
                if not text:
                    text = links.nth(i).get_attribute("aria-label") or ""
                href = (links.nth(i).get_attribute("href") or "")[:80]
                sel = _build_selector_for(links.nth(i))
                label = f"{text} ({href})" if href else text
                elements.append({
                    "tag": tag,
                    "role": "link",
                    "text": label[:80],
                    "selector": sel,
                })
            except Exception:
                continue
    except Exception:
        pass

    try:
        # --- Input fields ---
        inputs = page.locator(
            "input:not([type='submit']):not([type='button']):not([type='hidden']), "
            "textarea, [contenteditable='true']"
        )
        input_count = inputs.count()
        for i in range(min(input_count, 20)):
            try:
                tag = inputs.nth(i).evaluate("el => el.tagName.toLowerCase()")
                placeholder = inputs.nth(i).get_attribute("placeholder") or ""
                aria_label = inputs.nth(i).get_attribute("aria-label") or ""
                input_type = inputs.nth(i).get_attribute("type") or "text"
                label_text = placeholder or aria_label or input_type
                sel = _build_selector_for(inputs.nth(i))
                elements.append({
                    "tag": tag,
                    "role": "input",
                    "text": label_text[:60],
                    "selector": sel,
                })
            except Exception:
                continue
    except Exception:
        pass

    try:
        # --- Select / dropdown ---
        selects = page.locator("select")
        select_count = selects.count()
        for i in range(min(select_count, 10)):
            try:
                tag = "select"
                aria_label = selects.nth(i).get_attribute("aria-label") or ""
                # Get option text for context
                options = selects.nth(i).locator("option")
                opt_texts: list[str] = []
                opt_count = options.count()
                for j in range(min(opt_count, 8)):
                    try:
                        opt_texts.append(options.nth(j).inner_text().strip()[:40])
                    except Exception:
                        continue
                label = aria_label or f"select with {opt_count} options"
                sel = _build_selector_for(selects.nth(i))
                elements.append({
                    "tag": tag,
                    "role": "select",
                    "text": f"{label}: [{', '.join(opt_texts)}]",
                    "selector": sel,
                })
            except Exception:
                continue
    except Exception:
        pass

    return elements


def _build_selector_for(locator: Any) -> str:
    """Build a Playwright-compatible selector for an element.

    Tries in order:
    1. ``data-testid`` attribute
    2. ``id`` attribute (if it looks stable — not a random UUID)
    3. ``aria-label`` attribute
    4. Visible text-based selector (``:text()``) as last resort
    Falls back to a generic tag-based selector if nothing works.
    """
    try:
        # Try data-testid
        test_id = locator.get_attribute("data-testid")
        if test_id:
            return f"[data-testid='{test_id}']"
    except Exception:
        pass

    try:
        # Try id (only if it looks stable — not a UUID or long hash)
        elem_id = locator.get_attribute("id")
        if elem_id and len(elem_id) < 20 and not re.match(
            r"^[a-f0-9]{8,}$", elem_id
        ):
            return f"#{elem_id}"
    except Exception:
        pass

    try:
        # Try aria-label
        aria = locator.get_attribute("aria-label")
        if aria:
            safe_aria = aria.replace("'", "\\'")
            return f"[aria-label='{safe_aria}']"
    except Exception:
        pass

    try:
        # Try text content for buttons / links
        tag = locator.evaluate("el => el.tagName.toLowerCase()")
        text = locator.inner_text().strip()[:60]
        if text and tag in ("button", "a", "span"):
            safe_text = text.replace("'", "\\'")
            return f"{tag}:text('{safe_text}')"
    except Exception:
        pass

    return _generic_selector_fallback(locator)


def _generic_selector_fallback(locator: Any) -> str:
    """Generate a generic CSS selector based on tag, class, and nth-of-type."""
    try:
        tag = locator.evaluate("el => el.tagName.toLowerCase()")
        # Try with the first CSS class
        cls = locator.get_attribute("class")
        if cls:
            first_cls = cls.split()[0]
            return f"{tag}.{first_cls}"
        return tag
    except Exception:
        return "*"


# ===========================================================================
# Serialisation helper — convert CalendarEvent list to LLM-action-friendly dicts
# ===========================================================================


def _events_to_action_dicts(events: list[CalendarEvent]) -> list[dict[str, Any]]:
    """Convert ``CalendarEvent`` objects to plain dicts for ``done`` action payloads."""
    return [
        {
            "date": e.date,
            "name": e.name,
            "datetime": e.datetime.isoformat(),
            "duration_hours": e.duration_hours,
        }
        for e in events
    ]
