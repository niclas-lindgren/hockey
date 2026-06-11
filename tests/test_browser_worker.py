"""Unit tests for credential-leak sanitization in browser_worker.py."""

from tournament_scheduler.pipeline.browser_worker import (
    _redact_credentials,
    _sanitize_html,
)


class TestSanitizeHtml:
    def test_strips_password_input_value(self):
        html = '<input type="password" id="pass" name="pass" value="secret123">'
        result = _sanitize_html(html)
        assert "secret123" not in result
        assert 'value=""' in result

    def test_strips_email_input_value(self):
        html = '<input id="email" type="text" value="user@example.com">'
        result = _sanitize_html(html)
        assert "user@example.com" not in result
        assert 'value=""' in result

    def test_leaves_unrelated_input_values_untouched(self):
        html = '<input type="text" id="other" value="hello">'
        assert _sanitize_html(html) == html

    def test_leaves_checkbox_value_untouched(self):
        html = '<input type="checkbox" name="remember" value="1" checked>'
        assert _sanitize_html(html) == html

    def test_empty_html_returns_empty(self):
        assert _sanitize_html("") == ""

    def test_strips_username_input_by_name(self):
        html = '<input name="username" value="myuser">'
        result = _sanitize_html(html)
        assert "myuser" not in result
        assert 'value=""' in result


class TestRedactCredentials:
    def test_redacts_email_when_env_var_set(self, monkeypatch):
        monkeypatch.setenv("BOOKUP_EMAIL", "user@example.com")
        monkeypatch.delenv("BOOKUP_PASSWORD", raising=False)
        text = 'text input (placeholder=user@example.com)'
        result = _redact_credentials(text)
        assert "user@example.com" not in result
        assert "[REDACTED]" in result

    def test_redacts_password_when_env_var_set(self, monkeypatch):
        monkeypatch.setenv("BOOKUP_PASSWORD", "SuperSecret123")
        monkeypatch.delenv("BOOKUP_EMAIL", raising=False)
        text = 'text input (placeholder=SuperSecret123)'
        result = _redact_credentials(text)
        assert "SuperSecret123" not in result
        assert "[REDACTED]" in result

    def test_no_op_when_env_vars_unset(self, monkeypatch):
        monkeypatch.delenv("BOOKUP_EMAIL", raising=False)
        monkeypatch.delenv("BOOKUP_PASSWORD", raising=False)
        text = "some label text with no credentials"
        assert _redact_credentials(text) == text

    def test_empty_text_returns_empty(self, monkeypatch):
        monkeypatch.setenv("BOOKUP_EMAIL", "user@example.com")
        assert _redact_credentials("") == ""
