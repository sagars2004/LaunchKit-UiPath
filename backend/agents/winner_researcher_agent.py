"""
Past Winner Researcher Agent.

Searches Devpost for similar past submissions, scrapes top results,
and synthesizes winner patterns via Gemini.

Inputs: hackathon_name (str), track_category (str)
Outputs: WinnerPatterns
"""

import json
import logging

from backend.models.intelligence import WinnerPatterns
from backend.services.devpost_service import DevpostService, get_devpost_service
from backend.services.llm_service import LLMService, get_llm_service
from backend.services.prompt_loader import load_prompt

logger = logging.getLogger("launchkit.agent.winner")


class WinnerResearcherAgent:
    """Research past Devpost winners and extract submission patterns."""

    def __init__(
        self,
        llm: LLMService | None = None,
        gemini: LLMService | None = None,
        devpost: DevpostService | None = None,
    ) -> None:
        self.llm = llm or gemini or get_llm_service()
        self.devpost = devpost or get_devpost_service()

    async def run(self, hackathon_name: str, track_category: str = "") -> WinnerPatterns:
        query = f"{hackathon_name} {track_category}".strip()
        scraped: list[dict] = []

        try:
            urls = await self.devpost.search_submissions(query, limit=5)
            for url in urls:
                try:
                    data = await self.devpost.scrape_submission_page(url)
                    scraped.append(data)
                except Exception as exc:
                    logger.warning("Failed to scrape %s: %s", url, exc)
        except Exception as exc:
            logger.warning("Winner research scraping failed: %s", exc)

        if not scraped:
            return WinnerPatterns(
                hackathon_name=hackathon_name,
                submissions_analyzed=0,
                framing_recommendations=[
                    "No past submissions found — rely on hackathon criteria directly",
                ],
            )

        prompt = load_prompt("winner_research")
        user_prompt = prompt.render_user(
            hackathon_name=hackathon_name,
            scraped_submissions=json.dumps(scraped, indent=2),
        )

        try:
            result = await self.llm.generate_structured(
                prompt=user_prompt,
                output_schema=WinnerPatterns,
                system_prompt=prompt.system,
            )
            result.hackathon_name = hackathon_name
            result.submissions_analyzed = len(scraped)
            return result
        except Exception as exc:
            logger.warning("Gemini synthesis failed, returning empty patterns: %s", exc)
            return WinnerPatterns(
                hackathon_name=hackathon_name,
                submissions_analyzed=len(scraped),
            )
