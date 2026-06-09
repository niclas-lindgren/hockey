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


# ===========================================================================
# LLM agent loop — LLMGuidedScraper
# ===========================================================================

# LLM client – optional dependency; graceful degradation when unavailable
try:
    from ..llm.lm_studio_client import LMStudioClient, LMStudioUnavailableError

    _LLM_AVAILABLE = True
except ImportError:
    _LLM_AVAILABLE = False
    LMStudioUnavailableError = RuntimeError


# Default endpoint — Pi overrides this via the extension
_DEFAULT_LLM_ENDPOINT = "http://host.lima.internal:1234"


class LLMGuidedScraper:
    """Agentic scraper that uses an LLM to navigate JS-rendered calendars.

    The scraper opens a URL with Playwright, captures a simplified DOM
    snapshot, sends it to the LLM, executes the returned action (click,
    select, type, wait, scroll, or done), and loops until calendar events
    are extracted or the iteration limit is hit.

    The LLM endpoint is configurable and **not hardcoded** — Pi passes its
    configured endpoint through the extension. The scraper defaults to
    ``LMStudioClient`` but can accept any compatible client that exposes
    a ``complete(system, user, temperature)`` method.

    Parameters
    ----------
    llm_endpoint:
        Base URL for the LLM API (e.g. ``http://host.lima.internal:1234``).
        Ignored if *client* is provided.
    llm_model:
        Model name to use (e.g. ``"qwen2.5-32b-instruct"``).
    client:
        A pre-configured LLM client instance. If provided, *llm_endpoint*
        and *llm_model* are ignored. The client must expose a
        ``complete(system, user, temperature)`` method returning an object
        with a ``text`` attribute.
    max_iterations:
        Maximum number of LLM-guided interaction cycles before the scraper
        blocks with a Norwegian message.
    """

    def __init__(
        self,
        llm_endpoint: str = _DEFAULT_LLM_ENDPOINT,
        llm_model: str = "qwen2.5-32b-instruct",
        client: Any | None = None,
        max_iterations: int = 20,
    ) -> None:
        self.max_iterations = max_iterations

        if client is not None:
            self._client = client
        else:
            self._client = LMStudioClient(
                base_url=llm_endpoint,
                model=llm_model,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        url: str,
        name: str,
        start_date: datetime,
        end_date: datetime,
        *,
        max_iterations: int | None = None,
    ) -> list[CalendarEvent]:
        """Run the LLM-guided agent loop for a single calendar source.

        Opens *url* with Playwright (headless Chromium), captures a DOM
        snapshot, sends it to the LLM with context about ice hall bookings,
        executes the returned action, and repeats until the LLM signals
        ``done`` with extracted events or the iteration limit is hit.

        Parameters
        ----------
        url:
            Target URL to open.
        name:
            Human-readable source name (for prompts and logging).
        start_date / end_date:
            Date range the LLM should search within.
        max_iterations:
            Override the instance-level default for this call.

        Returns
        -------
        list[CalendarEvent]
            Extracted events, or empty list if the scraper blocked.

        Raises
        ------
        RuntimeError
            If ``LMStudioClient`` is unavailable (import failed).
        """
        if not _LLM_AVAILABLE:
            raise RuntimeError(
                "LLM-guided scraper er ikke tilgjengelig — "
                "LMStudioClient kunne ikke importeres. "
                "Sjekk at lm_studio_client.py finnes i tournament_scheduler/llm/."
            )

        iterations = max_iterations if max_iterations is not None else self.max_iterations
        logger.info(
            "Starter LLM-guided skraping for '%s' (%s) — maks %d iterasjoner",
            name, url, iterations,
        )

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("Playwright is not installed — cannot run LLM-guided scraper")
            return []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                page.goto(url, timeout=30_000, wait_until="networkidle")
            except Exception as exc:
                logger.warning("Kunne ikke laste %s: %s", url, exc)
                # Still try — the page may have partial content
                try:
                    page.goto(url, timeout=30_000)
                except Exception as exc2:
                    logger.error("Giving up on %s: %s", url, exc2)
                    browser.close()
                    return []

            page.wait_for_timeout(2_000)  # Let JS render

            for iteration in range(1, iterations + 1):
                logger.debug("Iterasjon %d/%d for '%s'", iteration, iterations, name)

                # --- Step 2: Capture DOM snapshot ---
                snapshot = capture_dom_snapshot(page)

                # --- Step 3: Send snapshot to LLM ---
                system_prompt = _build_system_prompt(name, start_date, end_date)
                user_message = _build_user_message(
                    snapshot=snapshot,
                    source_name=name,
                    start_date=start_date,
                    end_date=end_date,
                    iteration=iteration,
                    max_iterations=iterations,
                )

                try:
                    response = self._client.complete(
                        system=system_prompt,
                        user=user_message,
                        temperature=0.1,
                    )
                    raw_text = response.text.strip()
                    logger.debug("LLM response (iter %d): %s", iteration, raw_text[:300])
                except Exception as exc:
                    logger.error(
                        "LLM-feil i iterasjon %d for '%s': %s",
                        iteration, name, exc,
                    )
                    continue

                # --- Step 4: Parse the action ---
                try:
                    # Try to extract JSON from markdown fences or raw
                    json_text = _extract_json_from_llm(raw_text)
                    action_data = json.loads(json_text)
                    action = action_from_dict(action_data)
                except (ValueError, json.JSONDecodeError) as exc:
                    logger.warning(
                        "Kunne ikke tolke LLM-svar som handling (iter %d): %s",
                        iteration, exc,
                    )
                    continue

                # --- Step 5/6: Execute the action ---
                if action.action == "done":
                    events = _action_events_to_calendar_events(action.events)
                    logger.info(
                        "LLM signaliserte ferdig for '%s' — %d hendelser funnet",
                        name, len(events),
                    )
                    browser.close()
                    return events

                success = _execute_action(action, page)
                if not success:
                    logger.warning(
                        "Handling '%s' feilet for '%s' (iter %d)",
                        action.action, name, iteration,
                    )
                    # Continue anyway — the LLM may adapt

                page.wait_for_timeout(1_500)  # Let the page settle

            # --- Step 7: Max iterations exceeded — block ---
            final_snapshot = capture_dom_snapshot(page)
            block_message = (
                f"\n### BLOCKERT: {name}\n"
                f"Kilden '{name}' ({url}) returnerte 0 hendelser etter "
                f"{iterations} iterasjoner med LLM-styrt navigasjon.\n\n"
                f"**Siste sidetilstand:**\n"
                f"- Tittel: {final_snapshot.get('title', 'ukjent')}\n"
                f"- URL: {final_snapshot.get('url', url)}\n"
                f"- Viewport: {final_snapshot.get('viewport_width', '?')}x"
                f"{final_snapshot.get('viewport_height', '?')}\n"
                f"- Synlige elementer: {final_snapshot.get('element_count', 0)}\n"
                f"- Synlig tekst (første 500 tegn):\n"
                f"{final_snapshot.get('visible_text', '')[:500]}\n"
            )
            logger.warning(block_message)
            print(block_message)  # Also surface to user

            browser.close()
            return []


def _build_system_prompt(
    source_name: str,
    start_date: datetime,
    end_date: datetime,
) -> str:
    """Build the system prompt describing ice hall bookings and available actions."""
    # Build the prompt using raw string to avoid escaping JSON examples
    lines: list[str] = [
        'Du er en agent som navigerer ishall-kalendere for aa finne bookinger.',
        '',
        '**Hva du ser etter:**',
        'Ishall-bookinger ser typisk slik ut:',
        "- Datoer med tidsluker (f.eks. '08:00-09:30' eller 'kl 08.00-09.30')",
        "- Holdnavn som 'Kongsberghallen', 'Jarhallen', 'Baerum ishall'",
        "- Lag-/klubbnavn som 'Kongsberg', 'Jar', 'Jutul', 'Skien'",
        "- Aktiviteter som 'ishockey', 'kunstlop', 'trening', 'kamp'",
        '- Manedsoversikter med ukedager og datoer',
        '',
        '**Dine mulige handlinger:**',
        '1. **click** -- Klikk paa en knapp eller lenke.',
        '   Bruk: {"action": "click", "selector": "button:text(\'Vis kalender\')"}',
        '2. **select** -- Velg et alternativ i en nedtrekksmeny.',
        '   Bruk: {"action": "select", "selector": "select#month", "value": "2026-01"}',
        '3. **type** -- Skriv tekst i et input-felt.',
        '   Bruk: {"action": "type", "selector": "input[type=\'date\']", "value": "2026-01-01"}',
        '4. **wait** -- Vent i et gitt antall millisekunder.',
        '   Bruk: {"action": "wait", "ms": 2000}',
        '5. **scroll** -- Rull siden opp eller ned.',
        '   Bruk: {"action": "scroll", "direction": "down", "amount": 300}',
        '6. **extract** -- Trekk ut kalenderdata fra den synlige teksten.',
        '   Bruk: {"action": "extract"}',
        '7. **done** -- Signaliser at du er ferdig og returner hendelser.',
        '   Bruk: {"action": "done", "events": [...]}',
        '',
        '**Regler:**',
        '- Svar ALLTID med et JSON-objekt -- ingen forklarende tekst utenfor JSON.',
        "- Hvis kalenderdata ikke er synlig, prov aa klikke paa knapper som 'Vis kalender',",
        "  'Kalender', 'Book tid', 'Ledige tider', eller lignende.",
        '- Hvis du ser en manedsvisning, prov aa navigere til riktig maned/ar.',
        '- Hvis du finner kalenderdata i tabellform, bruk **extract** for aa faa dem ut.',
        '- Naar du har hentet ut alle hendelser, returner **done** med events-listen.',
        '- Hver hendelse skal inneholde: date (DD.MM.AAAA), name (beskrivelse),',
        '  duration_hours (antall timer som desimaltall).',
        '- **Ikke** gi opp etter en feilet handling -- prov forskjellige tilnaerminger.',
        f'- **Maalperiode:** {start_date.strftime("%d.%m.%Y")} til {end_date.strftime("%d.%m.%Y")}',
        f'- **Kilde:** {source_name}',
    ]
    return '\n'.join(lines)


def _build_user_message(
    snapshot: dict[str, Any],
    source_name: str,
    start_date: datetime,
    end_date: datetime,
    iteration: int,
    max_iterations: int,
) -> str:
    """Build the user message containing the DOM snapshot and context."""
    lines: list[str] = [
        f"Iterasjon {iteration}/{max_iterations} for '{source_name}'",
        f"Målperiode: {start_date.strftime('%d.%m.%Y')} til {end_date.strftime('%d.%m.%Y')}",
        "",
        "--- DOM-øyeblikksbilde ---",
        f"Tittel: {snapshot.get('title', 'ukjent')}",
        f"URL: {snapshot.get('url', 'ukjent')}",
        f"Viewport: {snapshot.get('viewport_width', '?')}x{snapshot.get('viewport_height', '?')} piksler",
        f"Antall interaktive elementer: {snapshot.get('element_count', 0)}",
        "",
        "Synlig tekst:",
        snapshot.get('visible_text', '(ingen synlig tekst)'),
        "",
        "Interaktive elementer:",
    ]

    elements = snapshot.get("interactive_elements", [])
    if elements:
        for i, elem in enumerate(elements):
            lines.append(
                f"  [{i}] <{elem.get('tag', '?')}> role={elem.get('role', '?')} "
                f"text=\"{elem.get('text', '')[:80]}\" "
                f"selector={elem.get('selector', '?')}"
            )
    else:
        lines.append("  (ingen interaktive elementer funnet)")

    lines.append("")
    lines.append("Hva vil du gjøre? Svar med et JSON-objekt.")

    return "\n".join(lines)


def _extract_json_from_llm(raw_text: str) -> str:
    """Extract valid JSON from an LLM response, stripping markdown fences.

    Handles both `` ```json `` and `` ``` `` fences, and also finds JSON
    objects embedded in prose with ``{...}`` extraction.
    """
    text = raw_text.strip()

    # Strip markdown code fences
    for fence in ("```json", "```"):
        if text.startswith(fence):
            text = text[len(fence):].strip()
            if text.endswith("```"):
                text = text[:-3].strip()
            break

    # For action responses, try to find a JSON object if there's surrounding prose
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]

    return text.strip()


def _execute_action(action: LLMAction, page: Any) -> bool:
    """Execute a single LLM action on the Playwright page.

    Returns ``True`` if the action was executed successfully (or if the
    error is non-fatal), ``False`` if the action clearly failed and the
    LLM should try a different approach.
    """
    try:
        if action.action == "click":
            if not action.selector:
                logger.warning("click-handling mangler selector")
                return False
            element = page.locator(action.selector)
            if element.count() == 0:
                logger.warning("Fant ikke element med selector '%s'", action.selector)
                return False
            element.first.click()
            logger.debug("Klikket på '%s'", action.selector)
            return True

        elif action.action == "select":
            if not action.selector or not action.value:
                return False
            element = page.locator(action.selector)
            if element.count() == 0:
                return False
            element.first.select_option(action.value)
            logger.debug("Valgte '%s' i '%s'", action.value, action.selector)
            return True

        elif action.action == "type":
            if not action.selector:
                return False
            element = page.locator(action.selector)
            if element.count() == 0:
                return False
            element.first.fill(action.value)
            logger.debug("Fylte inn '%s' i '%s'", action.value[:20], action.selector)
            return True

        elif action.action == "wait":
            import time

            ms = max(action.ms, 100)  # Minimum 100ms
            time.sleep(ms / 1000.0)
            logger.debug("Venter i %d ms", ms)
            return True

        elif action.action == "scroll":
            direction = action.direction or "down"
            amount = action.amount or 300
            if direction == "down":
                page.evaluate(f"window.scrollBy(0, {amount})")
            elif direction == "up":
                page.evaluate(f"window.scrollBy(0, -{amount})")
            elif direction == "left":
                page.evaluate(f"window.scrollBy(-{amount}, 0)")
            elif direction == "right":
                page.evaluate(f"window.scrollBy({amount}, 0)")
            else:
                page.evaluate(f"window.scrollBy(0, {amount})")
            logger.debug("Scroller %s %d piksler", direction, amount)
            return True

        elif action.action == "extract":
            # extract is handled by capturing visible text;
            # the LLM will include the extracted data in a subsequent
            # ``done`` action. Nothing to execute on the page.
            logger.debug("extract-handling — samler synlig tekst")
            return True

        elif action.action == "done":
            # The caller handles ``done`` before calling this function
            logger.debug("done-handling — skal ikke kjøres via _execute_action")
            return True

        else:
            logger.warning("Ukjent handlingstype: '%s'", action.action)
            return False

    except Exception as exc:
        logger.warning(
            "Feil ved utføring av '%s'-handling: %s",
            action.action, exc,
        )
        return False


def _action_events_to_calendar_events(
    event_dicts: list[dict[str, Any]],
) -> list[CalendarEvent]:
    """Convert event dicts from an LLM ``done`` action to CalendarEvent objects."""
    events: list[CalendarEvent] = []
    for item in event_dicts:
        if not isinstance(item, dict):
            continue
        date_str = item.get("date", "")
        name = item.get("name", "")
        duration = float(item.get("duration_hours", 1.0))
        if not date_str or not name:
            continue
        try:
            dt = datetime.strptime(date_str, "%d.%m.%Y")
        except ValueError:
            # Try ISO format
            try:
                dt = datetime.fromisoformat(date_str)
            except (ValueError, TypeError):
                continue
        events.append(
            CalendarEvent(
                date=dt.strftime("%d.%m.%Y"),
                name=name,
                datetime=dt,
                duration_hours=duration,
            )
        )
    return events
