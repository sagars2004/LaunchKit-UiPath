"""
Retrospective Agent.

Generates a post-submission lessons-learned report from metrics and context.

Inputs: metrics_history, hackathon_brief, artifacts_summary
Outputs: retrospective markdown (str)
"""

import json
import logging

from backend.core.exceptions import AgentError
from backend.models.intelligence import HackathonBrief
from backend.services.llm_service import LLMService, get_llm_service
from backend.services.prompt_loader import load_prompt

logger = logging.getLogger("launchkit.agent.retrospective")


class RetrospectiveAgent:
    """Generate post-hackathon retrospective report."""

    def __init__(self, llm: LLMService | None = None, gemini: LLMService | None = None) -> None:
        self.llm = llm or gemini or get_llm_service()

    async def run(
        self,
        metrics_history: list[dict],
        hackathon_brief: dict | HackathonBrief,
        artifacts_summary: str = "",
    ) -> str:
        if isinstance(hackathon_brief, HackathonBrief):
            brief_json = hackathon_brief.model_dump_json()
        else:
            brief_json = json.dumps(hackathon_brief)

        prompt = load_prompt("retrospective")
        user_prompt = prompt.render_user(
            metrics_history=json.dumps(metrics_history, indent=2, default=str),
            hackathon_brief=brief_json,
            artifacts_summary=artifacts_summary or "No artifact summary provided",
        )

        try:
            return await self.llm.generate_text(
                prompt=user_prompt,
                system_prompt=prompt.system,
                temperature=0.6,
            )
        except Exception as exc:
            raise AgentError("Retrospective generation failed", str(exc)) from exc
