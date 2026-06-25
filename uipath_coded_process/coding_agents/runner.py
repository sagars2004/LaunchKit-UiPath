"""Invoke external coding CLIs (Claude Code, Cursor, Codex, Gemini CLI)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass

from coding_agents.types import CODING_TOOLS, CodingTool

JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


class CodingAgentError(RuntimeError):
    """Raised when a coding CLI fails or returns unparseable output."""


@dataclass
class CodingAgentResult:
    tool: CodingTool
    raw_output: str
    parsed: dict


def extract_json_object(text: str) -> dict:
    """Extract a JSON object from CLI stdout (plain JSON or fenced block)."""
    stripped = text.strip()
    if not stripped:
        raise CodingAgentError("Coding agent returned empty output")

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    fence_match = JSON_FENCE_RE.search(stripped)
    if fence_match:
        return json.loads(fence_match.group(1))

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return json.loads(stripped[start : end + 1])

    raise CodingAgentError("Could not parse JSON from coding agent output")


def _cursor_binary() -> str:
    for name in ("agent", "cursor-agent"):
        if shutil.which(name):
            return name
    return "agent"


def _build_command(tool: CodingTool, prompt: str, repo_path: str) -> list[str]:
    """Build CLI argv for the selected coding tool."""
    env_override = os.environ.get(f"LAUNCHKIT_{tool.upper()}_CMD")
    if env_override:
        return env_override.format(prompt=prompt, repo_path=repo_path).split()

    if tool == "claude":
        return ["claude", "-p", prompt, "--output-format", "text"]
    if tool == "cursor":
        # Cursor CLI is `agent` (not `cursor`). See https://cursor.com/docs/cli/headless
        return [_cursor_binary(), "-p", "--output-format", "json", prompt]
    if tool == "codex":
        return ["codex", "exec", "--full-auto", prompt]
    if tool == "gemini":
        return ["gemini", "-p", prompt]
    raise CodingAgentError(f"Unsupported coding tool: {tool}")


def _resolve_binary(tool: CodingTool, command: list[str]) -> None:
    if shutil.which(command[0]) is None:
        raise CodingAgentError(
            f"{command[0]} not found on PATH. Install {tool} CLI or set "
            f"LAUNCHKIT_{tool.upper()}_CMD to a custom command."
        )


class CodingAgentRunner:
    """Run repo analysis through an external coding agent CLI."""

    def __init__(self, timeout_seconds: float = 300.0) -> None:
        self.timeout_seconds = timeout_seconds

    def analyze_repo(
        self,
        *,
        tool: CodingTool,
        prompt: str,
        repo_path: str,
    ) -> CodingAgentResult:
        if tool not in CODING_TOOLS:
            raise CodingAgentError(f"tool must be one of {CODING_TOOLS}")

        command = _build_command(tool, prompt, repo_path)
        _resolve_binary(tool, command)

        try:
            completed = subprocess.run(
                command,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise CodingAgentError(
                f"{tool} timed out after {self.timeout_seconds}s"
            ) from exc

        output = (completed.stdout or "").strip()
        if not output and completed.stderr:
            output = completed.stderr.strip()

        if completed.returncode != 0:
            detail = completed.stderr.strip() or output or f"exit code {completed.returncode}"
            raise CodingAgentError(f"{tool} failed: {detail}")

        parsed = extract_json_object(output)
        return CodingAgentResult(tool=tool, raw_output=output, parsed=parsed)
