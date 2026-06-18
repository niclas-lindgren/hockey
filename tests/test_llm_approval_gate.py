"""Unit tests for tournament_scheduler.pipeline.llm_approval_gate."""

from unittest.mock import MagicMock

from tournament_scheduler.pipeline.llm_approval_gate import ApprovalVerdict, run_approval_gate


def make_mock_client(text: str):
    """Return a mock LMStudioClient whose complete() returns an object with .text."""
    mock = MagicMock()
    mock.complete.return_value.text = text
    return mock


def test_go_verdict_json():
    client = make_mock_client(
        '{"decision": "GO", "rationale": "Plan looks good", "blockers": [], "proposed_changes": []}'
    )
    result = run_approval_gate({"plan": {"tournaments": []}, "rules_report": []}, client)
    assert result.decision == "GO"
    assert result.rationale == "Plan looks good"
    assert result.blockers == []
    assert result.proposed_changes == []


def test_no_go_verdict_with_blockers_json():
    client = make_mock_client(
        '{"decision": "NO_GO", "rationale": "Issues found", '
        '"blockers": ["Missing age group U7", "Host imbalance"], '
        '"proposed_changes": ["Add U7 tournament"]}'
    )
    result = run_approval_gate({"plan": {"tournaments": []}, "rules_report": []}, client)
    assert result.decision == "NO_GO"
    assert result.rationale == "Issues found"
    assert result.blockers == ["Missing age group U7", "Host imbalance"]
    assert result.proposed_changes == ["Add U7 tournament"]


def test_malformed_json_text_fallback_go():
    client = make_mock_client("GO - the plan is acceptable")
    result = run_approval_gate({"plan": {"tournaments": []}, "rules_report": []}, client)
    assert result.decision == "GO"
    assert result.blockers == []


def test_malformed_json_text_fallback_no_go():
    client = make_mock_client("NO_GO - too many issues")
    result = run_approval_gate({"plan": {"tournaments": []}, "rules_report": []}, client)
    assert result.decision == "NO_GO"
    assert result.blockers == []


def test_completely_unparseable_defaults_to_go():
    client = make_mock_client("gibberish text with no decision keywords here")
    result = run_approval_gate({"plan": {"tournaments": []}, "rules_report": []}, client)
    assert result.decision == "GO"


def test_json_in_markdown_fence():
    client = make_mock_client(
        '```json\n{"decision": "GO", "rationale": "Looks good", "blockers": [], "proposed_changes": []}\n```'
    )
    result = run_approval_gate({"plan": {"tournaments": []}, "rules_report": []}, client)
    assert result.decision == "GO"
    assert result.rationale == "Looks good"


def test_plan_summary_built_from_checkpoint():
    """Verify that the user prompt includes tournament count and rules_report issues."""
    plan_checkpoint = {
        "plan": {
            "tournaments": [
                {"host": "Host 1", "age_group": "U12", "date": "2025-01-10"},
                {"host": "Host 2", "age_group": "U10", "date": "2025-02-07"},
            ]
        },
        "rules_report": [
            {
                "regel": "Rule 1",
                "forklaring": "Advarsel: Missing U7 coverage",
                "kategori": "Advarsel",
            }
        ],
    }

    mock_client = MagicMock()
    mock_client.complete.return_value.text = (
        '{"decision": "GO", "rationale": "Acceptable", "blockers": [], "proposed_changes": []}'
    )

    run_approval_gate(plan_checkpoint, mock_client)

    # The user prompt is passed as keyword arg 'user'
    call_kwargs = mock_client.complete.call_args[1]
    user_prompt: str = call_kwargs["user"]

    # Should mention 2 tournaments
    assert '"tournaments_count": 2' in user_prompt
    # Should surface the Advarsel issue in the issues list
    assert "Advarsel: Missing U7 coverage" in user_prompt
