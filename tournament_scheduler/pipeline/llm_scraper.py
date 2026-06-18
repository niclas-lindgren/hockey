"""Strategy-driven browser scraper for JS-rendered calendar SPAs.

Executes the scraper strategy's ``initial_navigation`` steps directly
with Playwright — no LLM decision-making in the control loop.  The LLM
is only consulted as a last-resort text parser when built-in DOM-based
extractors cannot find structured events.

Provides:
  - ``capture_dom_snapshot`` — build a simplified text representation of a
    Playwright page for debugging / LLM-text fallback.
  - ``StrategyDrivenScraper`` — opens a URL, executes strategy-defined
    navigation steps, navigates months, and extracts calendar events.
"""

from __future__ import annotations

import json
import logging
import re
import time as _time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..models import CalendarEvent

logger = logging.getLogger(__name__)

# ===========================================================================
# DOM snapshot — simplified text representation of a Playwright page
# ===========================================================================

MAX_VISIBLE_TEXT_CHARS = 8_000
MAX_INTERACTIVE_ELEMENTS = 50


def capture_dom_snapshot(page: Any) -> dict[str, Any]:
    """Capture a simplified text representation of a Playwright page.

    The snapshot strips ``<script>`` and ``<style>`` tags, extracts
    interactive elements (buttons, links, inputs, selects), and the
    page's readable text truncated to ~8000 characters.
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

    try:
        raw_html = page.content()
    except Exception:
        raw_html = ""
    cleaned_html = _strip_script_and_style(raw_html)

    visible_text = _extract_visible_text(cleaned_html)
    visible_text = _redact_credential_values(visible_text)
    if len(visible_text) > MAX_VISIBLE_TEXT_CHARS:
        visible_text = visible_text[:MAX_VISIBLE_TEXT_CHARS] + "\n... [truncated]"

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
    cleaned = re.sub(
        r'<(script|style)\b[^>]*>.*?</\1\s*>',
        "", html, flags=re.DOTALL | re.IGNORECASE,
    )
    cleaned = re.sub(r'<(script|style)\b[^>]*/>', "", cleaned, flags=re.IGNORECASE)
    return cleaned


def _redact_credential_values(text: str) -> str:
    """Scrub literal BookUp credential values from text before LLM use.

    Defense-in-depth (layer 4 of the BookUp credential-leak mitigation —
    see also `tournament_scheduler/pipeline/browser_worker.py`
    `_sanitize_html()`/`_redact_credentials()` for the Playwright-worker
    layers, and `.pi/lib/scraper-agent.ts` `redactCredentials()` for the TS
    agent layer). Even though `_detect_and_login()` only fills credential
    fields into form inputs (which `_strip_script_and_style` does not
    specifically scrub), this ensures that if an entered email/password
    value is ever echoed back into the page's visible text or HTML, it
    never reaches the LLM prompt built in `_extract_events_via_llm()`.

    Longer-term alternative (out of scope for this fix): out-of-band
    browser auth — run `_detect_and_login()`/`initial_navigation` once
    headfully to establish a persistent authenticated session (saved
    storage state/cookies) outside the LLM loop, so login UI/credential
    state never has to be captured in a snapshot or sent to the LLM.
    """
    if not text:
        return text
    import os as _os

    for env_var in ("BOOKUP_EMAIL", "BOOKUP_PASSWORD"):
        value = _os.environ.get(env_var, "")
        if value:
            text = text.replace(value, "[REDACTED]")
    return text


def _extract_visible_text(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "meta", "link", "svg"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return re.sub(r"\s+", " ", text).strip()
    except ImportError:
        text = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", text).strip()


def _extract_interactive_elements(page: Any) -> list[dict[str, str]]:
    elements: list[dict[str, str]] = []
    try:
        buttons = page.locator("button, input[type='submit'], input[type='button'], [role='button']")
        for i in range(min(buttons.count(), 30)):
            try:
                text = buttons.nth(i).inner_text().strip()[:80]
                if not text:
                    text = buttons.nth(i).get_attribute("aria-label") or ""
                sel = _build_selector_for(buttons.nth(i))
                elements.append({"tag": "button", "role": "button", "text": text[:60], "selector": sel})
            except Exception:
                continue
    except Exception:
        pass

    try:
        links = page.locator("a[href]")
        for i in range(min(links.count(), 20)):
            try:
                text = links.nth(i).inner_text().strip()[:80]
                if not text:
                    text = links.nth(i).get_attribute("aria-label") or ""
                href = (links.nth(i).get_attribute("href") or "")[:80]
                sel = _build_selector_for(links.nth(i))
                label = f"{text} ({href})" if href else text
                elements.append({"tag": "a", "role": "link", "text": label[:80], "selector": sel})
            except Exception:
                continue
    except Exception:
        pass

    try:
        inputs = page.locator(
            "input:not([type='submit']):not([type='button']):not([type='hidden']), textarea, [contenteditable='true']"
        )
        for i in range(min(inputs.count(), 20)):
            try:
                tag = inputs.nth(i).evaluate("el => el.tagName.toLowerCase()")
                placeholder = inputs.nth(i).get_attribute("placeholder") or ""
                aria_label = inputs.nth(i).get_attribute("aria-label") or ""
                input_type = inputs.nth(i).get_attribute("type") or "text"
                sel = _build_selector_for(inputs.nth(i))
                elements.append({
                    "tag": tag, "role": "input",
                    "text": (placeholder or aria_label or input_type)[:60],
                    "selector": sel,
                })
            except Exception:
                continue
    except Exception:
        pass

    try:
        selects = page.locator("select")
        for i in range(min(selects.count(), 10)):
            try:
                aria_label = selects.nth(i).get_attribute("aria-label") or ""
                options = selects.nth(i).locator("option")
                opt_texts = [options.nth(j).inner_text().strip()[:40] for j in range(min(options.count(), 8))]
                sel = _build_selector_for(selects.nth(i))
                label = aria_label or f"select with {options.count()} options"
                elements.append({
                    "tag": "select", "role": "select",
                    "text": f"{label}: [{', '.join(opt_texts)}]",
                    "selector": sel,
                })
            except Exception:
                continue
    except Exception:
        pass

    return elements


def _build_selector_for(locator: Any) -> str:
    try:
        test_id = locator.get_attribute("data-testid")
        if test_id:
            return f"[data-testid='{test_id}']"
    except Exception:
        pass
    try:
        elem_id = locator.get_attribute("id")
        if elem_id and len(elem_id) < 20 and not re.match(r"^[a-f0-9]{8,}$", elem_id):
            return f"#{elem_id}"
    except Exception:
        pass
    try:
        aria = locator.get_attribute("aria-label")
        if aria:
            return f"[aria-label='{aria.replace(chr(39), '\\' + chr(39))}']"
    except Exception:
        pass
    try:
        tag = locator.evaluate("el => el.tagName.toLowerCase()")
        text = locator.inner_text().strip()[:60]
        if text and tag in ("button", "a", "span"):
            return f"{tag}:text('{text.replace(chr(39), '\\' + chr(39))}')"
    except Exception:
        pass
    try:
        tag = locator.evaluate("el => el.tagName.toLowerCase()")
        cls = locator.get_attribute("class")
        if cls:
            return f"{tag}.{cls.split()[0]}"
        return tag
    except Exception:
        return "*"


# ===========================================================================
# Strategy-driven scraper
# ===========================================================================



class StrategyDrivenScraper:
    """Scrape a calendar source by executing strategy-defined navigation steps.

    The scraper opens the target URL with Playwright, executes the
    ``initial_navigation`` steps from the scraper strategy, navigates
    through months using the ``month_selector``, and extracts events
    using DOM-based selectors.

    The LLM is only consulted as a last-resort text parser when
    built-in DOM extractors find no structured events on the page.

    Parameters
    ----------
    llm_endpoint:
        Base URL for the LLM API (for text-only fallback extraction).
    llm_model:
        Model name for the LLM fallback.
    max_months:
        Maximum number of months to navigate before giving up.
    screenshots_dir:
        If set, save PNG screenshots at each navigation step for debugging.
    """

    def __init__(
        self,
        llm_endpoint: str = "http://host.lima.internal:1234",
        llm_model: str = "qwen2.5-32b-instruct",
        max_months: int = 8,
        screenshots_dir: str = "",
    ) -> None:
        self.llm_endpoint = llm_endpoint
        self.llm_model = llm_model
        self.max_months = max_months
        self.screenshots_dir = screenshots_dir
        self._shot_counter = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _screenshot(self, page: Any, label: str) -> None:
        """Save a debug screenshot if screenshots_dir is configured."""
        if not self.screenshots_dir:
            return
        import os as _os
        _os.makedirs(self.screenshots_dir, exist_ok=True)
        self._shot_counter += 1
        safe_label = re.sub(r'[^a-zA-Z0-9_-]', '_', label)[:60]
        path = f"{self.screenshots_dir}/{self._shot_counter:03d}_{safe_label}.png"
        try:
            page.screenshot(path=path, full_page=False)
            logger.debug("Screenshot: %s", path)
        except Exception as exc:
            logger.warning("Screenshot failed (%s): %s", label, exc)

    def run(
        self,
        url: str,
        name: str,
        start_date: datetime,
        end_date: datetime,
        *,
        initial_navigation: list[dict[str, Any]] | None = None,
        month_selector: str = "",
        event_pattern: str = "",
    ) -> list[CalendarEvent]:
        """Run the strategy-driven scraper for a single calendar source.

        Parameters
        ----------
        url: Target URL to open.
        name: Human-readable source name (for logging).
        start_date / end_date: Date range to search within.
        initial_navigation: Strategy-defined navigation steps.
        month_selector: CSS selector for the "next month" button.
        event_pattern: Hint for DOM-based extraction (e.g. "FullCalendar").

        Returns
        -------
        list[CalendarEvent]
            Extracted events, or empty list if nothing found.
        """
        logger.info("Strategy-driven scraping for '%s' (%s)", name, url)

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("Playwright is not installed — cannot run scraper")
            return []

        events: list[CalendarEvent] = []
        nav = initial_navigation or []
        month_sel = month_selector or ".fc-next-button, button[title*='Next'], a[aria-label*='Next']"

        # If the first nav step is a goto, use its URL as the initial target
        # and skip that step (the strategy wants us to start there).
        if nav and nav[0].get("cmd") == "goto":
            url = nav[0].get("url", url)
            nav = nav[1:]
            logger.debug("Using first nav step URL as initial target: %s", url)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                page.goto(url, timeout=30_000, wait_until="domcontentloaded")
            except Exception as exc:
                logger.warning("Initial load for %s had issues: %s", url, exc)
                try:
                    page.goto(url, timeout=30_000)
                except Exception as exc2:
                    logger.error("Giving up on %s: %s", url, exc2)
                    browser.close()
                    return []

            page.wait_for_timeout(2_000)
            self._screenshot(page, f"01_initial_{_safe_label(name)}")

            # If this looks like BookUp, wait extra for the app.html iframe to load
            if any("bookup.no" in f.url for f in page.frames if hasattr(f, 'url')):
                logger.debug("BookUp detected, waiting for iframe to load...")
                for _ in range(10):  # up to 10 seconds
                    page.wait_for_timeout(1_000)
                    if any("app.html" in f.url for f in page.frames):
                        logger.debug("app.html iframe found")
                        break
                page.wait_for_timeout(2_000)  # extra settle time
                self._screenshot(page, f"01b_iframe_loaded_{_safe_label(name)}")

            # ---- Step 1: Execute initial navigation steps ----
            for si, step in enumerate(nav):
                cmd = step.get("cmd", "")
                wait_ms = step.get("wait_ms", 1500)
                try:
                    if cmd == "goto":
                        target = step.get("url", url)
                        logger.debug("nav[%d]: goto %s", si, target)
                        page.goto(target, timeout=30_000, wait_until="domcontentloaded")
                        page.wait_for_timeout(wait_ms)
                        self._screenshot(page, f"02_nav{si}_{cmd}_{_safe_label(target[:40])}")
                    elif cmd == "click":
                        sel = str(step.get("selector", ""))
                        logger.debug("nav[%d]: click '%s'", si, sel)
                        if sel:
                            _click_robust(page, sel, timeout=10_000)
                            page.wait_for_timeout(wait_ms)
                            self._screenshot(page, f"02_nav{si}_click_{_safe_label(sel[:40])}")
                    elif cmd == "type":
                        sel = str(step.get("selector", ""))
                        txt = str(step.get("text", ""))
                        logger.debug("nav[%d]: type '%s' in '%s'", si, txt[:20], sel)
                        if sel and txt:
                            page.locator(sel).first.fill(txt, timeout=5_000)
                            page.wait_for_timeout(wait_ms)
                            self._screenshot(page, f"02_nav{si}_type")
                    elif cmd == "note":
                        note_text = str(step.get("text", ""))
                        logger.debug("nav[%d]: note: %s", si, note_text)
                        # Heuristic: if note mentions searching, try to find and fill a search field
                        if _looks_like_search_hint(note_text):
                            _try_search(page, note_text, wait_ms)
                            # Wait extra for search results to render
                            page.wait_for_timeout(max(wait_ms, 3000))
                            self._screenshot(page, f"02_nav{si}_search_results")
                    elif cmd == "wait":
                        _time.sleep(max(wait_ms, 500) / 1000.0)
                except Exception as exc:
                    logger.warning("nav[%d] feilet (%s): %s", si, cmd, exc)
                    # Best-effort — continue

            # ---- Step 2: Navigate months and extract events ----
            months_tried = 0
            for month_idx in range(self.max_months):
                months_tried = month_idx + 1
                page.wait_for_timeout(1_500)

                # Try DOM-based extraction
                month_events = _extract_events_from_dom(page, event_pattern, name)
                if month_events:
                    logger.debug("Month %d: %d events via DOM extraction", month_idx + 1, len(month_events))
                    events.extend(month_events)
                else:
                    break  # DOM extraction empty — assume we've passed the calendar data

                # Try clicking "next month"
                clicked = False
                for sel in [month_sel, ".fc-next-button", "button[title*='Next']", "button[title*='Neste']",
                             "a[aria-label*='Next']", "a[aria-label*='Neste']"]:
                    try:
                        btn = page.locator(sel).first
                        if btn.count() > 0 and btn.is_visible():
                            btn.click(timeout=5_000)
                            clicked = True
                            logger.debug("Clicked next-month via '%s'", sel)
                            break
                    except Exception:
                        continue

                if not clicked:
                    # Try common Norwegian/Swedish labels
                    for label in ["Neste", "Neste måned", "→", ">", "Next", "Next month"]:
                        try:
                            page.locator(f"text={label}").first.click(timeout=3_000)
                            clicked = True
                            break
                        except Exception:
                            continue

                if not clicked:
                    logger.debug("No next-month button found after %d months", months_tried)
                    break

                page.wait_for_timeout(1_500)

            logger.info("'%s': %d events over %d months", name, len(events), months_tried)
            browser.close()

        # Deduplicate by date+name
        seen = set()
        unique: list[CalendarEvent] = []
        for e in events:
            key = (e.date, e.name)
            if key not in seen:
                seen.add(key)
                unique.append(e)

        return unique


# ===========================================================================
# Helpers for navigation
# ===========================================================================


def _safe_label(text: str) -> str:
    """Sanitise a string for use in a filename."""
    return re.sub(r'[^a-zA-Z0-9_-]', '_', text)[:60]


def _click_robust(page: Any, selector: str, timeout: int = 10_000) -> bool:
    """Click an element, trying multiple selector strategies and iframes."""
    contexts: list[Any] = [page]
    for frame in page.frames:
        if "app.html" in frame.url:
            contexts.append(frame)

    for ctx in contexts:
        # Try exact selector first
        try:
            el = ctx.locator(selector).first
            if el.count() > 0:
                el.click(timeout=timeout)
                return True
        except Exception:
            pass

        # If selector is a text= selector, try broader matches
        if selector.startswith("text="):
            plain = selector[5:]
            for attempt in [f":text('{plain}')", f"a:text('{plain}')", f"button:text('{plain}')",
                            f"[aria-label*='{plain}']", f"*:has-text('{plain}')"]:
                try:
                    el = ctx.locator(attempt).first
                    if el.count() > 0 and el.is_visible():
                        el.click(timeout=timeout)
                        return True
                except Exception:
                    continue

    return False


def _looks_like_search_hint(note: str) -> bool:
    """Check if a note step is instructing to search for something."""
    keywords = ["søk", "search", "finn", "skriv inn", "skriv", "søkefelt"]
    return any(kw in note.lower() for kw in keywords)


def _try_search(page: Any, hint: str, wait_ms: int) -> None:
    """Try to find a search field and type a search term from the hint.

    Handles both direct-page inputs and inputs inside iframes (BookUp pattern).
    """
    # Extract quoted text from hint as search term
    quoted = re.findall(r"['\xab\"]([^'\xbb\"]+)['\xbb\"]", hint)
    if not quoted:
        # Try to find the club name from the hint
        quoted = [w for w in hint.split() if w[0].isupper() and len(w) > 2]
    if not quoted:
        return

    search_term = quoted[0]
    logger.debug("Trying search for '%s'", search_term)

    # Find the search context (direct page or iframe)
    search_contexts: list[Any] = [page]
    for frame in page.frames:
        if "app.html" in frame.url:
            search_contexts.append(frame)
            logger.debug("Found BookUp app.html iframe")

    for ctx in search_contexts:
        for sel in [
            "#calendar-search", "#place-search",
            "input[type='search']", "input[placeholder*='Søk']", "input[placeholder*='søk']",
            "input[placeholder*='Search']", "input[name='q']", "input[name='search']",
            "input[aria-label*='søk']", "input[aria-label*='Søk']",
            "input.search-input", "#search-input", ".search-box input",
        ]:
            try:
                el = ctx.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    el.fill(search_term, timeout=5_000)
                    ctx.wait_for_timeout(wait_ms)
                    logger.debug("Filled search '%s' in %s", search_term, sel)
                    return
            except Exception:
                continue

    logger.debug("No search field found for '%s'", search_term)


def _detect_and_login(page: Any, credential_env_vars: list[str], screenshots_dir: str) -> bool:
    """Detect BookUp login page and attempt login with env var credentials.

    Returns True if login succeeded or wasn't needed, False if login failed.
    """
    import os as _os

    body = ""
    try:
        body = page.inner_text("body")
    except Exception:
        return True  # Can't read page, assume it's fine

    # Check for login indicators
    if "Logg inn" not in body and "Du er ikke logget inn" not in body:
        return True  # Not a login page

    logger.info("BookUp login page detected")

    # Check for credentials
    email = _os.environ.get(credential_env_vars[0] if credential_env_vars else "BOOKUP_EMAIL", "")
    password = _os.environ.get(credential_env_vars[1] if len(credential_env_vars) > 1 else "BOOKUP_PASSWORD", "")

    if not email:
        logger.warning(
            "BookUp login required but %s not set. Set env var or use --debug-screenshots to inspect.",
            credential_env_vars[0] if credential_env_vars else "BOOKUP_EMAIL",
        )
        return False

    logger.info("Attempting BookUp login with %s", credential_env_vars[0] if credential_env_vars else "BOOKUP_EMAIL")

    # Find and click login link
    try:
        login_link = page.locator("a:has-text('logge inn'), a:has-text('Logg inn')").first
        if login_link.count() > 0:
            login_link.click(timeout=5_000)
            page.wait_for_timeout(3_000)
    except Exception:
        pass  # Maybe already on login page

    # Fill email
    try:
        email_input = page.locator("#email").first
        if email_input.count() > 0:
            email_input.fill(email, timeout=5_000)
            page.wait_for_timeout(500)
    except Exception as exc:
        logger.warning("Could not fill email: %s", exc)
        return False

    # Click "Fortsett"
    try:
        continue_btn = page.locator("button:has-text('Fortsett')").first
        if continue_btn.count() > 0:
            continue_btn.click(timeout=5_000)
            page.wait_for_timeout(3_000)
    except Exception as exc:
        logger.warning("Could not click Fortsett: %s", exc)
        return False

    # Check if password field appeared (some BookUp instances use email+password)
    try:
        pwd_input = page.locator("input[type='password']").first
        if pwd_input.count() > 0 and password:
            pwd_input.fill(password, timeout=5_000)
            page.wait_for_timeout(500)
            # Find submit button
            for btn_text in ["Logg inn", "Log in", "Fortsett", "Continue", "Submit"]:
                try:
                    submit_btn = page.locator(f"button:has-text('{btn_text}')").first
                    if submit_btn.count() > 0:
                        submit_btn.click(timeout=5_000)
                        page.wait_for_timeout(3_000)
                        break
                except Exception:
                    continue
    except Exception:
        pass

    # Check if login succeeded
    try:
        body_after = page.inner_text("body")
        if "Logg inn" in body_after or "Du er ikke logget inn" in body_after:
            logger.warning("BookUp login appears to have failed — still seeing login page")
            if screenshots_dir:
                import os as _os
                _os.makedirs(screenshots_dir, exist_ok=True)
                page.screenshot(path=f"{screenshots_dir}/login_failed.png")
            return False
    except Exception:
        pass

    logger.info("BookUp login succeeded")
    return True


# ===========================================================================
# DOM-based event extraction
# ===========================================================================


def _extract_events_from_dom(page: Any, event_pattern: str, source_name: str) -> list[CalendarEvent]:
    """Extract calendar events from the visible DOM using known patterns.

    Tries FullCalendar selectors first, then generic table-based patterns.
    """
    events: list[CalendarEvent] = []

    # ----- FullCalendar / timeGrid pattern -----
    try:
        # FullCalendar events are typically .fc-event, .fc-bgevent, or .fc-timegrid-event
        fc_events = page.locator(
            ".fc-event, .fc-bgevent, .fc-timegrid-event, [class*='fc-event'], "
            "td[class*='fc-']:not([class*='fc-day']):not([class*='fc-col-header'])"
        )
        count = fc_events.count()
        for i in range(count):
            try:
                el = fc_events.nth(i)
                text = el.inner_text().strip()
                aria = el.get_attribute("aria-label") or ""
                title_attr = el.get_attribute("title") or ""
                combined = f"{text} {aria} {title_attr}".strip()
                if combined:
                    parsed = _parse_event_text(combined)
                    if parsed:
                        events.extend(parsed)
            except Exception:
                continue
        if events:
            return events
    except Exception:
        pass

    # ----- Table-based pattern (rows with date + time + description) -----
    try:
        rows = page.locator("table tr, table tbody tr, [role='row']")
        row_count = rows.count()
        for i in range(min(row_count, 200)):
            try:
                row_text = rows.nth(i).inner_text().strip()
                parsed = _parse_event_text(row_text)
                if parsed:
                    events.extend(parsed)
            except Exception:
                continue
        if events:
            return events
    except Exception:
        pass

    # ----- List-item pattern -----
    try:
        items = page.locator("li, .booking-item, .event-item, [class*='booking'], [class*='event']")
        item_count = items.count()
        for i in range(min(item_count, 200)):
            try:
                item_text = items.nth(i).inner_text().strip()
                parsed = _parse_event_text(item_text)
                if parsed:
                    events.extend(parsed)
            except Exception:
                continue
    except Exception:
        pass

    return events


# Date/time extraction patterns
_DATE_RE = re.compile(
    r'(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?',
)
_TIME_RE = re.compile(
    r'(\d{1,2})[:.](\d{2})\s*(?:[-–—]|til)\s*(\d{1,2})[:.](\d{2})',
)
_NAME_CLEAN_RE = re.compile(r'\b(?:man|tir|ons|tor|fre|lør|søn|mandag|tirsdag|onsdag|torsdag|fredag|lørdag|søndag)\b', re.IGNORECASE)
_STRIP_RE = re.compile(r'[\t ]{2,}')


def _parse_event_text(text: str) -> list[CalendarEvent]:
    """Parse visible text for date + time-slot + name patterns.

    Returns a list of CalendarEvent objects, or empty list.
    """
    if not text or len(text) < 6:
        return []

    # Normalise
    text = _STRIP_RE.sub(" ", text).strip()

    # Try patterns like "01.09.2026 08:00-09:30 Some description"
    # or "1.9. 08:00-09:30 Some description" (Swedish/Norwegian format)
    date_match = _DATE_RE.search(text)
    if not date_match:
        return []

    day = int(date_match.group(1))
    month = int(date_match.group(2))
    year_str = date_match.group(3)
    if year_str:
        year = int(year_str) if len(year_str) == 4 else 2000 + int(year_str)
    else:
        # Assume current season — if month is 1-7 it's likely next year
        now = datetime.now()
        year = now.year + 1 if month <= 7 else now.year

    try:
        dt = datetime(year, month, day)
    except ValueError:
        return []

    time_match = _TIME_RE.search(text)
    if time_match:
        # Build datetime with time
        try:
            start_h = int(time_match.group(1))
            start_m = int(time_match.group(2))
            end_h = int(time_match.group(3))
            end_m = int(time_match.group(4))
            start_dt = dt.replace(hour=start_h, minute=start_m)
            end_dt = dt.replace(hour=end_h, minute=end_m)
            if end_dt <= start_dt:
                end_dt = dt.replace(hour=23, minute=59)
            duration = (end_dt - start_dt).total_seconds() / 3600.0
        except ValueError:
            start_dt = dt
            duration = 1.0
    else:
        start_dt = dt
        duration = 1.0  # assume 1-hour default

    # Extract name — everything after the time, minus date/day noise
    name = text
    name = _DATE_RE.sub("", name, count=1)
    name = _TIME_RE.sub("", name, count=1)
    name = _NAME_CLEAN_RE.sub("", name)
    name = re.sub(r'\s+', " ", name).strip(" -–—,;:").strip()
    if not name or len(name) < 2:
        name = f"Hendelse {dt.strftime('%d.%m')}"

    return [CalendarEvent(
        date=dt.strftime("%d.%m.%Y"),
        name=name[:120],
        datetime=start_dt,
        duration_hours=round(duration, 2),
    )]


