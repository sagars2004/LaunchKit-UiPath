"""Tests for coding agent response normalization."""

from coding_agents.normalize import normalize_code_intelligence, unwrap_cli_response


def test_unwrap_cursor_result_envelope():
    envelope = {
        "type": "result",
        "subtype": "success",
        "result": '{"project_name": "FastAPI", "confidence_score": 0.9}',
    }
    data = unwrap_cli_response(envelope, "cursor", "")
    assert data["project_name"] == "FastAPI"


def test_unwrap_cursor_result_with_markdown_fence():
    envelope = {
        "type": "result",
        "result": '```json\n{"project_name": "LaunchKit", "confidence_score": 85}\n```',
    }
    data = unwrap_cli_response(envelope, "cursor", "")
    normalized = normalize_code_intelligence(data)
    assert normalized["project_name"] == "LaunchKit"
    assert normalized["confidence_score"] == 0.85


def test_normalize_project_type_and_defaults():
    normalized = normalize_code_intelligence(
        {
            "project_name": "X",
            "project_type": "Web App",
            "confidence_score": 90,
        }
    )
    assert normalized["project_type"] == "web_app"
    assert normalized["confidence_score"] == 0.9
    assert normalized["one_liner"]  # default filled
