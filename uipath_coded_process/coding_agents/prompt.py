"""Prompt builder for repo analysis via external coding CLIs."""

from __future__ import annotations

import json


def build_analysis_prompt(
    *,
    file_tree: list[str],
    key_file_contents: str,
    hackathon_criteria_summary: str,
) -> str:
    """Build the analysis prompt sent to Claude Code, Cursor, Codex, or Gemini CLI."""
    tree_block = "\n".join(file_tree[:200])
    return f"""Analyze this GitHub repository for a hackathon submission.

## Hackathon Judging Criteria
{hackathon_criteria_summary}

## Repository File Tree
{tree_block}

## Key File Contents
{key_file_contents}

Produce ONLY a single JSON object (no markdown fences) with these fields:
- project_name, one_liner (≤15 words), project_type (web_app|cli_tool|api|library|ml_model|pipeline|other)
- primary_language, tech_stack (array)
- architecture_description (2-3 technical sentences)
- key_features (array of {{name, description, technical_detail, hackathon_relevance}})
- novel_approaches (array of strings)
- real_challenges (array of {{challenge, how_addressed}})
- impressive_code_patterns (array of strings)
- entry_points, api_endpoints, external_services_used (arrays)
- missing_or_incomplete (array — be honest)
- confidence_score (0.0-1.0 based on how much code you could analyze)

Rules:
- Be honest about limitations. Never invent functionality.
- Ground every claim in files you can see in this repository.
- Map technical decisions to the hackathon judging criteria.
"""


def criteria_summary_from_brief(hackathon_brief: dict) -> str:
    criteria = hackathon_brief.get("judging_criteria") or []
    return json.dumps(criteria, indent=2)
