"""Regression tests for registered-team search rendering."""

from tournament_scheduler.pipeline.registered_teams import render_registered_teams_html


def test_search_filters_individual_team_rows_inside_a_club():
    payload = {
        "generated_at": "2026-08-05T06:00:00Z",
        "total_teams": 3,
        "total_clubs": 1,
        "age_groups": [
            {
                "age_group": "U7",
                "clubs": [{"club": "Sandefjord", "teams": ["Sandefjord"]}],
            },
            {
                "age_group": "U8",
                "clubs": [{"club": "Sandefjord", "teams": ["Sandefjord"]}],
            },
            {
                "age_group": "U11",
                "clubs": [{"club": "Sandefjord", "teams": ["Sandefjord"]}],
            },
        ],
    }

    html = render_registered_teams_html(payload)

    assert 'data-club-search="sandefjord"' in html
    assert html.count('class="team"') == 3
    assert 'data-search="u7 sandefjord"' in html
    assert 'data-search="u8 sandefjord"' in html
    assert 'data-search="u11 sandefjord"' in html
    assert "club.querySelectorAll('.team')" in html
    assert "team.hidden = !teamMatch" in html
    assert "visibleTeams" in html
    assert "av ${allTeams} lag" in html
