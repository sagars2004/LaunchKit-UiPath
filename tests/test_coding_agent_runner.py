"""Tests for external coding CLI runner utilities."""

import pytest

from coding_agents.runner import CodingAgentError, extract_json_object


def test_extract_json_object_plain():
    data = extract_json_object('{"project_name": "LaunchKit", "confidence_score": 0.85}')
    assert data["project_name"] == "LaunchKit"
    assert data["confidence_score"] == 0.85


def test_extract_json_object_fenced():
    text = """Here is the analysis:
```json
{"project_name": "LaunchKit", "confidence_score": 0.9}
```
"""
    data = extract_json_object(text)
    assert data["project_name"] == "LaunchKit"


def test_extract_json_object_embedded():
    text = 'Analysis complete.\n{"project_name": "X", "confidence_score": 0.5}\nDone.'
    data = extract_json_object(text)
    assert data["project_name"] == "X"


def test_extract_json_object_empty_raises():
    with pytest.raises(CodingAgentError, match="empty"):
        extract_json_object("   ")


def test_cursor_command_uses_agent_binary(monkeypatch):
    monkeypatch.setenv("LAUNCHKIT_CURSOR_CMD", "")
    monkeypatch.setattr("coding_agents.runner.shutil.which", lambda name: "/usr/bin/agent" if name == "agent" else None)

    from coding_agents.runner import _build_command

    cmd = _build_command("cursor", "analyze this repo", "/tmp/repo")
    assert cmd[0] == "agent"
    assert "-p" in cmd
    assert "--output-format" in cmd
    assert "json" in cmd
