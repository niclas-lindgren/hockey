"""HTML template fragments for the season plan exporter.

Each fragment is a standalone file loaded at import time.
"""

from pathlib import Path

_TEMPLATE_DIR = Path(__file__).parent


def _load(name: str) -> str:
    """Load a template fragment from the templates directory."""
    return (_TEMPLATE_DIR / name).read_text(encoding="utf-8")


# Shared CSS for dark theme
STYLES_CSS = _load("styles.css")

# Navbar fragment (shared across pages)
NAVBAR = _load("navbar.html")

# Season plan specific sections
HEADER = _load("header.html")
SCORES = _load("scores.html")
METRICS = _load("metrics.html")
FILTERS = _load("filters.html")
COUNT_BAR = _load("count_bar.html")

# Team detail sections
TEAM_STATS = _load("team_stats.html")
TRAVEL_STATS = _load("travel_stats.html")
HEATMAP = _load("heatmap.html")
CLUB_DASHBOARD = _load("club_dashboard.html")
REVIEW_SUMMARY = _load("review_summary.html")

# Full page template (embeds all sections)
PAGE_TEMPLATE = _load("page_template.html")

# JavaScript for interactivity
JAVASCRIPT = _load("script.js")
