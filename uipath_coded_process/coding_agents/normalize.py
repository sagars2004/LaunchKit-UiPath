"""Normalize coding CLI output into LaunchKit CodeIntelligence shape."""

from __future__ import annotations

from coding_agents.runner import CodingAgentError, extract_json_object
from coding_agents.types import CodingTool

VALID_PROJECT_TYPES = {
    "web_app",
    "cli_tool",
    "api",
    "library",
    "ml_model",
    "pipeline",
    "other",
}

LIST_FIELDS = (
    "tech_stack",
    "novel_approaches",
    "impressive_code_patterns",
    "entry_points",
    "api_endpoints",
    "external_services_used",
    "missing_or_incomplete",
)


def unwrap_cli_response(parsed: dict, tool: CodingTool, raw_output: str) -> dict:
    """Extract CodeIntelligence JSON from tool-specific CLI envelopes."""
    if "project_name" in parsed:
        return parsed

    if tool == "cursor" and parsed.get("type") == "result":
        result_text = parsed.get("result", "")
        if isinstance(result_text, str) and result_text.strip():
            return extract_json_object(result_text)

    for key in ("result", "content", "output", "response", "text"):
        value = parsed.get(key)
        if isinstance(value, str) and value.strip():
            try:
                return extract_json_object(value)
            except CodingAgentError:
                continue
        if isinstance(value, dict) and "project_name" in value:
            return value

    try:
        return extract_json_object(raw_output)
    except CodingAgentError as exc:
        raise CodingAgentError(
            "Coding agent did not return CodeIntelligence JSON. "
            f"Got keys: {list(parsed.keys())}"
        ) from exc


def _normalize_project_type(value: object) -> str:
    if not value:
        return "other"
    normalized = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    if normalized in VALID_PROJECT_TYPES:
        return normalized
    if "web" in normalized:
        return "web_app"
    if "cli" in normalized:
        return "cli_tool"
    if "api" in normalized:
        return "api"
    if "library" in normalized or "lib" in normalized:
        return "library"
    if "ml" in normalized or "model" in normalized:
        return "ml_model"
    if "pipeline" in normalized:
        return "pipeline"
    return "other"


def _normalize_confidence(value: object) -> float:
    if value is None:
        return 0.5
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.5
    if score > 1.0:
        score = score / 100.0
    return max(0.0, min(1.0, score))


def _normalize_key_features(items: object) -> list[dict]:
    if not isinstance(items, list):
        return []
    features: list[dict] = []
    for item in items:
        if isinstance(item, dict):
            features.append(
                {
                    "name": str(item.get("name", "")),
                    "description": str(item.get("description", "")),
                    "technical_detail": str(item.get("technical_detail", "")),
                    "hackathon_relevance": str(item.get("hackathon_relevance", "")),
                }
            )
        elif isinstance(item, str):
            features.append(
                {
                    "name": item,
                    "description": "",
                    "technical_detail": "",
                    "hackathon_relevance": "",
                }
            )
    return features


def _normalize_challenges(items: object) -> list[dict]:
    if not isinstance(items, list):
        return []
    challenges: list[dict] = []
    for item in items:
        if isinstance(item, dict):
            challenges.append(
                {
                    "challenge": str(item.get("challenge", item.get("name", ""))),
                    "how_addressed": str(item.get("how_addressed", item.get("solution", ""))),
                }
            )
        elif isinstance(item, str):
            challenges.append({"challenge": item, "how_addressed": ""})
    return challenges


def _normalize_string_list(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(item) for item in items if item is not None]


def normalize_code_intelligence(data: dict) -> dict:
    """Coerce coding-agent output toward CodeIntelligence schema."""
    return {
        "project_name": str(data.get("project_name") or "Unknown Project"),
        "one_liner": str(data.get("one_liner") or data.get("tagline") or "Project analysis"),
        "project_type": _normalize_project_type(data.get("project_type")),
        "primary_language": str(data.get("primary_language") or "Unknown"),
        "tech_stack": _normalize_string_list(data.get("tech_stack")),
        "architecture_description": str(
            data.get("architecture_description") or data.get("architecture") or ""
        ),
        "key_features": _normalize_key_features(data.get("key_features")),
        "novel_approaches": _normalize_string_list(data.get("novel_approaches")),
        "real_challenges": _normalize_challenges(data.get("real_challenges")),
        "impressive_code_patterns": _normalize_string_list(data.get("impressive_code_patterns")),
        "entry_points": _normalize_string_list(data.get("entry_points")),
        "api_endpoints": _normalize_string_list(data.get("api_endpoints")),
        "external_services_used": _normalize_string_list(data.get("external_services_used")),
        "missing_or_incomplete": _normalize_string_list(data.get("missing_or_incomplete")),
        "confidence_score": _normalize_confidence(data.get("confidence_score")),
    }
