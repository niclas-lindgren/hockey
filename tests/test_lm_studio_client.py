"""Tests for tournament_scheduler.llm.lm_studio_client."""

import json
from unittest.mock import MagicMock, patch

import pytest

from tournament_scheduler.llm.lm_studio_client import (
    ConfidenceResult,
    LMStudioClient,
    LMStudioUnavailableError,
    LLMResponse,
    extract_confidence,
)


class TestLMStudioClient:
    def _mock_response(self, text: str, status: int = 200) -> MagicMock:
        """Build a mock urllib response context manager."""
        body = json.dumps({
            "choices": [{"message": {"content": text}}],
            "model": "qwen2.5-32b",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }).encode()
        cm = MagicMock()
        cm.__enter__ = lambda s: s
        cm.__exit__ = MagicMock(return_value=False)
        cm.read.return_value = body
        return cm

    def test_complete_returns_text(self):
        client = LMStudioClient(base_url="http://test.local:1234", model="test-model")
        mock_resp = self._mock_response('{"confidence": 0.9}')
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.complete("sys", "user")
        assert isinstance(result, LLMResponse)
        assert '{"confidence": 0.9}' in result.text

    def test_complete_records_token_counts(self):
        client = LMStudioClient(base_url="http://test.local:1234", model="test-model")
        mock_resp = self._mock_response("hello")
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.complete("sys", "user")
        assert result.prompt_tokens == 10
        assert result.completion_tokens == 5

    def test_complete_raises_on_network_error(self):
        import urllib.error

        client = LMStudioClient(base_url="http://test.local:1234", model="test-model")
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            with pytest.raises(LMStudioUnavailableError):
                client.complete("sys", "user")

    def test_complete_raises_on_invalid_json(self):
        cm = MagicMock()
        cm.__enter__ = lambda s: s
        cm.__exit__ = MagicMock(return_value=False)
        cm.read.return_value = b"not json"

        client = LMStudioClient(base_url="http://test.local:1234", model="test-model")
        with patch("urllib.request.urlopen", return_value=cm):
            with pytest.raises(LMStudioUnavailableError, match="non-JSON"):
                client.complete("sys", "user")


class TestExtractConfidence:
    def test_parses_valid_json(self):
        text = '{"confidence": 0.85, "valid": true, "reasoning": "Looks good"}'
        result = extract_confidence(text)
        assert result.confidence == pytest.approx(0.85)
        assert result.valid is True
        assert "Looks good" in result.reasoning

    def test_parses_json_in_markdown_fence(self):
        text = '```json\n{"confidence": 0.7, "valid": true, "reasoning": "ok"}\n```'
        result = extract_confidence(text)
        assert result.confidence == pytest.approx(0.7)

    def test_parses_json_embedded_in_prose(self):
        text = 'Sure! Here is my evaluation: {"confidence": 0.6, "valid": false, "reasoning": "empty"} Done.'
        result = extract_confidence(text)
        assert result.confidence == pytest.approx(0.6)
        assert result.valid is False

    def test_returns_low_confidence_on_parse_failure(self):
        result = extract_confidence("this is not json")
        assert result.confidence == 0.0
        assert result.valid is False

    def test_valid_defaults_to_true_for_high_confidence(self):
        text = '{"confidence": 0.9, "reasoning": "good"}'
        result = extract_confidence(text)
        assert result.valid is True

    def test_valid_defaults_to_false_for_low_confidence(self):
        text = '{"confidence": 0.3, "reasoning": "bad"}'
        result = extract_confidence(text)
        assert result.valid is False
