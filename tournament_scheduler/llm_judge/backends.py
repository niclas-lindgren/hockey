"""Concrete LLM judge backend implementations."""

import json
import os
import urllib.error
import urllib.request

from .interface import LLMJudge


class ClaudeJudgeBackend(LLMJudge):
    """Judge backend using the Anthropic Claude API via httpx-compatible urllib."""

    DEFAULT_MODEL = "claude-3-5-haiku-20241022"
    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or os.environ.get("RVV_CLAUDE_MODEL", self.DEFAULT_MODEL)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.api_key:
            raise RuntimeError(
                "ClaudeJudgeBackend requires ANTHROPIC_API_KEY environment variable."
            )

    def judge(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.API_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"Claude API returned HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Claude API connection failed: {exc.reason}") from exc

        try:
            return body["content"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Unexpected Claude API response shape: {body}") from exc


class OpenAIJudgeBackend(LLMJudge):
    """Judge backend using the OpenAI Chat Completions API."""

    DEFAULT_MODEL = "gpt-4o-mini"
    API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or os.environ.get("RVV_OPENAI_MODEL", self.DEFAULT_MODEL)
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError(
                "OpenAIJudgeBackend requires OPENAI_API_KEY environment variable."
            )

    def judge(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.API_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"OpenAI API returned HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI API connection failed: {exc.reason}") from exc

        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Unexpected OpenAI API response shape: {body}") from exc


class LLMBridgeJudgeBackend(LLMJudge):
    """Judge backend using a local LM Studio / llm-bridge OpenAI-compatible endpoint."""

    DEFAULT_HOST = "localhost"
    DEFAULT_PORT = 1234
    DEFAULT_MODEL = "local-model"

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        model: str | None = None,
    ) -> None:
        host = host or os.environ.get("RVV_LLM_BRIDGE_HOST", self.DEFAULT_HOST)
        port_str = os.environ.get("RVV_LLM_BRIDGE_PORT", str(self.DEFAULT_PORT))
        port = port or int(port_str)
        self.api_url = f"http://{host}:{port}/v1/chat/completions"
        self.model = model or os.environ.get("RVV_LLM_BRIDGE_MODEL", self.DEFAULT_MODEL)

    def judge(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "stream": False,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.api_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"LLM Bridge returned HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"LLM Bridge connection failed (is LM Studio running?): {exc.reason}"
            ) from exc

        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(
                f"Unexpected LLM Bridge response shape: {body}"
            ) from exc
