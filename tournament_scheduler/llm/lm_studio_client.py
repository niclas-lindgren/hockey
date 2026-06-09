"""HTTP client for an OpenAI-compatible chat completion API.

Provides:
  - LMStudioClient  — class-based client (injectable for testing)
  - complete()      — module-level convenience wrapper
  - extract_confidence() — parse a structured JSON confidence response
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_TEMPERATURE = 0.2
DEFAULT_TIMEOUT_SECONDS = 120


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class LLMResponse:
    """Parsed response from the LM Studio chat/completions endpoint."""

    text: str
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfidenceResult:
    """Parsed confidence assessment returned by the LLM."""

    confidence: float  # 0.0 – 1.0
    reasoning: str = ""
    valid: bool = True  # whether the LLM considers the data valid/usable
    raw_text: str = ""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class LMStudioClient:
    """Thin HTTP wrapper around the LM Studio OpenAI-compatible chat API.

    Parameters
    ----------
    base_url:
        Base URL of the OpenAI-compatible chat API server.
    model:
        Model identifier to use.
    timeout:
        Request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def complete(
        self,
        system: str,
        user: str,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> LLMResponse:
        """Send a chat completion request and return the assistant reply.

        Parameters
        ----------
        system:
            System prompt (context / persona for the LLM).
        user:
            User message (the actual question / data to analyse).
        temperature:
            Sampling temperature (default 0.2 for factual tasks).

        Returns
        -------
        LLMResponse
            Parsed response with the assistant text and token counts.

        Raises
        ------
        LMStudioUnavailableError
            When the server cannot be reached (network error or non-2xx).
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "stream": False,
        }

        raw = self._post("/v1/chat/completions", payload)

        choices = raw.get("choices", [])
        text = choices[0]["message"]["content"] if choices else ""

        usage = raw.get("usage", {})
        return LLMResponse(
            text=text,
            model=raw.get("model", self.model),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            raw=raw,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = self.base_url + path
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise LMStudioUnavailableError(
                f"Cannot reach LM Studio at {self.base_url}: {exc}"
            ) from exc
        except Exception as exc:
            raise LMStudioUnavailableError(
                f"Unexpected error calling LM Studio: {exc}"
            ) from exc

        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise LMStudioUnavailableError(
                f"LM Studio returned non-JSON response: {body[:200]}"
            ) from exc


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LMStudioUnavailableError(RuntimeError):
    """Raised when the LM Studio server cannot be reached or returns an error."""


def extract_confidence(response_text: str) -> ConfidenceResult:
    """Parse a structured JSON confidence block from an LLM response.

    The LLM is expected to return a JSON object (possibly embedded in prose)
    with at least::

        {
          "confidence": 0.85,
          "valid": true,
          "reasoning": "..."
        }

    If parsing fails the function returns a low-confidence result rather than
    raising, so callers can degrade gracefully.

    Parameters
    ----------
    response_text:
        Raw text from the LLM assistant reply.

    Returns
    -------
    ConfidenceResult
        Parsed fields; ``valid=False`` and ``confidence=0.0`` on parse failure.
    """
    # Try to locate a JSON block in the response.
    text = response_text.strip()

    # Strip markdown code fences if present
    for fence in ("```json", "```"):
        if text.startswith(fence):
            text = text[len(fence):]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            break

    # Find the first {...} block if the model added prose around it
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return ConfidenceResult(
            confidence=0.0,
            reasoning="Failed to parse LLM confidence response as JSON",
            valid=False,
            raw_text=response_text,
        )

    confidence = float(data.get("confidence", 0.0))
    valid = bool(data.get("valid", confidence >= 0.5))
    reasoning = str(data.get("reasoning", data.get("reason", "")))

    return ConfidenceResult(
        confidence=confidence,
        valid=valid,
        reasoning=reasoning,
        raw_text=response_text,
    )
