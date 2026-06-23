"""
Hackathon Intelligence Agent.

Scrapes a hackathon event page, extracts judging criteria, and structures
the result via Gemini into a HackathonBrief.

Inputs: hackathon_url (str)
Outputs: HackathonBrief
"""

import logging

from backend.core.exceptions import AgentError, ValidationError, format_agent_error
from backend.models.intelligence import HackathonBrief
from backend.services.devpost_service import DevpostService, get_devpost_service
from backend.services.llm_service import LLMService, get_llm_service
from backend.services.prompt_loader import load_prompt

logger = logging.getLogger("launchkit.agent.intel")


class HackathonIntelAgent:
    """Scrape hackathon page and produce structured HackathonBrief."""

    def __init__(
        self,
        llm: LLMService | None = None,
        gemini: LLMService | None = None,
        devpost: DevpostService | None = None,
    ) -> None:
        self.llm = llm or gemini or get_llm_service()
        self.devpost = devpost or get_devpost_service()

    async def run(self, hackathon_url: str) -> HackathonBrief:
        if not hackathon_url or not hackathon_url.startswith("http"):
            raise ValidationError("Invalid hackathon URL", "hackathon_url must be a valid HTTP URL")

        try:
            raw_text = await self.devpost.scrape_event_page(hackathon_url)
        except AgentError:
            raise
        except Exception as exc:
            raise AgentError("Failed to scrape hackathon page", str(exc)) from exc

        prompt = load_prompt("hackathon_intel")
        user_prompt = prompt.render_user(
            raw_page_text=raw_text,
            hackathon_url=hackathon_url,
        )

        try:
            return await self.llm.generate_structured(
                prompt=user_prompt,
                output_schema=HackathonBrief,
                system_prompt=prompt.system,
            )
        except Exception as exc:
            raise AgentError(
                "Failed to parse hackathon brief",
                format_agent_error(exc),
            ) from exc
