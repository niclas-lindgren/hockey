"""Shared helpers for the not-started/empty-input pipeline state."""

from __future__ import annotations

from html import escape

NOT_STARTED_MESSAGE = "Ikke begynt: påmeldingstiden er ikke over ennå."


def render_not_started_html(message: str = NOT_STARTED_MESSAGE) -> str:
    """Return the public placeholder page shown when no teams are registered."""
    html = (
        "<!doctype html>"
        "<html lang=\"nb\">"
        "<head>"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{escape(message)}</title>"
        "<style>"
        "body{margin:0;display:grid;place-items:center;min-height:100vh;"
        "background:linear-gradient(135deg,#eef4f8,#f8fafc);"
        "font:16px/1.6 system-ui,-apple-system,'Segoe UI',sans-serif;"
        "color:#24323d;}"
        "main{max-width:640px;margin:2rem;padding:3rem;text-align:center;"
        "background:#fff;border:1px solid #d9e2ea;border-radius:16px;"
        "box-shadow:0 16px 40px rgba(0,0,0,.08);}"
        ".icon{width:64px;height:64px;margin:0 auto 1.5rem;"
        "border-radius:50%;background:#3c5f79;color:#fff;"
        "display:grid;place-items:center;font-size:2rem;font-weight:700;}"
        "h1{margin:0;color:#1d2c37;font-size:2rem;}"
        "p{margin:1rem 0 0;color:#5b6874;font-size:1.05rem;}"
        "code{padding:.15em .45em;background:#eef3f7;border-radius:5px;"
        "font-family:ui-monospace,monospace;}"
        "</style>"
        "</head>"
        "<body>"
        "<main>"
        "<div class=\"icon\">🏒</div>"
        f"<h1>{escape(message)}</h1>"
        "</main>"
        "</body>"
        "</html>\n"
    )
    return html
