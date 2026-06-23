"""
Revision Agent.

Revises a submission artifact based on developer feedback and quality scores.
Combines the base revision prompt with artifact-type context.

Inputs: artifact_type, original_content, feedback, quality_scores, hackathon_brief
Outputs: revised content (str)
"""

import json
import logging

from backend.core.exceptions import AgentError, ValidationError
from backend.models.intelligence import HackathonBrief
from backend.services.llm_service import LLMService, get_llm_service
from backend.services.prompt_loader import load_prompt

logger = logging.getLogger("launchkit.agent.revision")

ARTIFACT_PROMPT_MAP = {
    "readme": "readme_generation",
    "devpost_copy": "devpost_copy",
    "demo_script": "demo_script",
    "social_content": "social_linkedin",
    "blog_draft": "blog_draft",
}


class RevisionAgent:
    """Revise a submission artifact based on feedback and quality scores."""

    def __init__(self, llm: LLMService | None = None, gemini: LLMService | None = None) -> None:
        self.llm = llm or gemini or get_llm_service()

    async def run(
        self,
        artifact_type: str,
        original_content: str,
        feedback: str,
        quality_scores: dict,
        hackathon_brief: dict | HackathonBrief,
    ) -> str:
        if not original_content:
            raise ValidationError("original_content is required", "Cannot revise empty artifact")
        if not feedback:
            raise ValidationError("feedback is required", "Provide developer feedback to revise")

        if isinstance(hackathon_brief, HackathonBrief):
            brief_json = hackathon_brief.model_dump_json()
        else:
            brief_json = json.dumps(hackathon_brief)

        base_prompt = load_prompt("revision_base")
        user_prompt = base_prompt.render_user(
            artifact_type=artifact_type,
            original_content=original_content,
            developer_feedback=feedback,
            quality_scores=json.dumps(quality_scores, indent=2),
            hackathon_brief=brief_json,
        )

        context_note = ""
        type_prompt_name = ARTIFACT_PROMPT_MAP.get(artifact_type)
        if type_prompt_name:
            try:
                type_prompt = load_prompt(type_prompt_name)
                context_note = f"\n\nOriginal generation guidelines:\n{type_prompt.system[:500]}"
            except FileNotFoundError:
                pass

        try:
            return await self.llm.generate_text(
                prompt=user_prompt,
                system_prompt=base_prompt.system + context_note,
                temperature=0.5,
            )
        except Exception as exc:
            raise AgentError(f"Revision failed for {artifact_type}", str(exc)) from exc
