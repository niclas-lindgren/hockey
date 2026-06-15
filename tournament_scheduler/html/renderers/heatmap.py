"""Heatmap colour-map helpers for the season-plan HTML report.

Builds the dark/light club colour maps that are injected as JSON
into the heatmap template fragment.
"""

from __future__ import annotations


_club_colors_dark = [
    {"bg": "#1a3a5c", "text": "#64b5f6"},
    {"bg": "#1b3a1b", "text": "#81c784"},
    {"bg": "#3a2e0a", "text": "#ffd54f"},
    {"bg": "#2a1a3a", "text": "#ba68c8"},
    {"bg": "#3a1a1a", "text": "#e57373"},
    {"bg": "#0a2a3a", "text": "#4dd0e1"},
    {"bg": "#3a3a0a", "text": "#fff176"},
    {"bg": "#1a3a2a", "text": "#aed581"},
    {"bg": "#3a1a0a", "text": "#ff8a65"},
]

_club_colors_light = [
    {"bg": "#dbeafe", "text": "#1d4ed8"},  # blue
    {"bg": "#dcfce7", "text": "#15803d"},  # green
    {"bg": "#fef3c7", "text": "#b45309"},  # amber
    {"bg": "#ede9fe", "text": "#6d28d9"},  # purple
    {"bg": "#ffe4e6", "text": "#be123c"},  # rose
    {"bg": "#cffafe", "text": "#0e7490"},  # cyan
    {"bg": "#fef9c3", "text": "#a16207"},  # yellow
    {"bg": "#ecfccb", "text": "#4d7c0f"},  # lime
    {"bg": "#ffedd5", "text": "#c2410c"},  # orange
]


def build_club_color_maps(heatmap_clubs: list[str]) -> dict[str, dict[str, dict[str, str]]]:
    """Build dark and light colour maps for the given list of clubs.

    Returns a dict structured as ``{"dark": {club: {"bg": ..., "text": ...}, ...},
    "light": {club: {"bg": ..., "text": ...}, ...}}``.
    """
    club_color_map_dark = {
        club: _club_colors_dark[i % len(_club_colors_dark)]
        for i, club in enumerate(heatmap_clubs)
    }
    club_color_map_light = {
        club: _club_colors_light[i % len(_club_colors_light)]
        for i, club in enumerate(heatmap_clubs)
    }
    return {"dark": club_color_map_dark, "light": club_color_map_light}
