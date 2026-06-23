"""Prompt template loader — loads from backend/prompts/*.txt with variable substitution."""

import re
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

_SYSTEM_MARKER = "SYSTEM:"
_USER_MARKER = "USER:"


class PromptTemplate:
    """Parsed prompt with system and user sections."""

    def __init__(self, name: str, system: str, user: str) -> None:
        self.name = name
        self.system = system.strip()
        self.user = user.strip()

    def render_user(self, **variables: str) -> str:
        return _substitute(self.user, variables)

    def render_system(self, **variables: str) -> str:
        return _substitute(self.system, variables)


def _substitute(template: str, variables: dict[str, str]) -> str:
    result = template
    for key, value in variables.items():
        result = result.replace("{" + key + "}", str(value))
    # Only flag placeholders that look like our template variables (snake_case)
    expected = set(re.findall(r"\{([a-z][a-z0-9_]*)\}", template))
    provided = set(variables.keys())
    missing = expected - provided
    if missing:
        raise ValueError(f"Unresolved prompt variables: {sorted(missing)}")
    return result


def load_prompt(name: str) -> PromptTemplate:
    """Load a prompt template by filename (without .txt extension)."""
    path = PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")

    raw = path.read_text(encoding="utf-8")

    if _SYSTEM_MARKER not in raw or _USER_MARKER not in raw:
        raise ValueError(f"Prompt {name} must contain SYSTEM: and USER: sections")

    system_part, user_part = raw.split(_USER_MARKER, 1)
    system = system_part.split(_SYSTEM_MARKER, 1)[1]

    return PromptTemplate(name=name, system=system, user=user_part)


def list_prompts() -> list[str]:
    return [p.stem for p in PROMPTS_DIR.glob("*.txt")]
