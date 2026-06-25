"""Shared types for coding agent integrations."""

from typing import Literal

CodingTool = Literal["claude", "cursor", "codex", "gemini"]

CODING_TOOLS: tuple[CodingTool, ...] = ("claude", "cursor", "codex", "gemini")
