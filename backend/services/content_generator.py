"""Content generation — produces all 5 submission artifacts via LLM."""

import asyncio
import json
import logging

from backend.models.content import DemoScript, DevpostCopy, SocialContent
from backend.services.llm_service import LLMService, get_llm_service
from backend.services.prompt_loader import load_prompt

logger = logging.getLogger("launchkit.content")


class ContentGenerator:
    """Generate README, Devpost copy, demo script, social, and blog artifacts."""

    def __init__(self, llm: LLMService | None = None, gemini: LLMService | None = None) -> None:
        self.llm = llm or gemini or get_llm_service()

    async def generate_all(
        self,
        code_intelligence: dict,
        hackathon_brief: dict,
        winning_brief: dict,
    ) -> dict[str, str]:
        """Generate all 5 artifacts concurrently. Returns type → content string."""
        ci = json.dumps(code_intelligence, indent=2)
        hb = json.dumps(hackathon_brief, indent=2)
        wb = json.dumps(winning_brief, indent=2)

        tasks = {
            "readme": self._generate_readme(ci, hb, wb),
            "devpost_copy": self._generate_devpost(ci, hb, wb),
            "demo_script": self._generate_demo(ci, hb, wb),
            "social_content": self._generate_social(ci, hb),
            "blog_draft": self._generate_blog(ci, hb, wb),
        }

        keys = list(tasks.keys())
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        artifacts: dict[str, str] = {}
        for key, result in zip(keys, results, strict=True):
            if isinstance(result, Exception):
                logger.error("Generation failed for %s: %s", key, result)
                artifacts[key] = f"[Generation failed: {result}]"
            else:
                artifacts[key] = result
        return artifacts

    async def _generate_readme(self, ci: str, hb: str, wb: str) -> str:
        prompt = load_prompt("readme_generation")
        user = prompt.render_user(
            code_intelligence=ci,
            hackathon_brief=hb,
            winning_brief=wb,
        )
        return await self.llm.generate_text(user, prompt.system, temperature=0.7)

    async def _generate_devpost(self, ci: str, hb: str, wb: str) -> str:
        prompt = load_prompt("devpost_copy")
        user = prompt.render_user(
            code_intelligence=ci,
            hackathon_brief=hb,
            winning_brief=wb,
        )
        result = await self.llm.generate_structured(
            user, DevpostCopy, prompt.system, temperature=0.7
        )
        return result.model_dump_json(indent=2)

    async def _generate_demo(self, ci: str, hb: str, wb: str) -> str:
        prompt = load_prompt("demo_script")
        user = prompt.render_user(
            code_intelligence=ci,
            hackathon_brief=hb,
            winning_brief=wb,
        )
        result = await self.llm.generate_structured(
            user, DemoScript, prompt.system, temperature=0.7
        )
        return result.model_dump_json(indent=2)

    async def _generate_social(self, ci: str, hb: str) -> str:
        prompt = load_prompt("social_linkedin")
        user = prompt.render_user(code_intelligence=ci, hackathon_brief=hb)
        result = await self.llm.generate_structured(
            user, SocialContent, prompt.system, temperature=0.8
        )
        return result.model_dump_json(indent=2)

    async def _generate_blog(self, ci: str, hb: str, wb: str) -> str:
        prompt = load_prompt("blog_draft")
        user = prompt.render_user(
            code_intelligence=ci,
            hackathon_brief=hb,
            winning_brief=wb,
        )
        return await self.llm.generate_text(user, prompt.system, temperature=0.7)


async def generate_winning_brief(
    hackathon_brief: dict,
    winner_patterns: dict,
    llm: LLMService | None = None,
    gemini: LLMService | None = None,
) -> dict:
    """Generate winning brief from intel + winner patterns."""
    from backend.models.intelligence import WinningBrief

    llm = llm or gemini or get_llm_service()
    prompt = load_prompt("winning_brief")
    user = prompt.render_user(
        hackathon_brief=json.dumps(hackathon_brief, indent=2),
        winner_patterns=json.dumps(winner_patterns, indent=2),
    )
    result = await llm.generate_structured(user, WinningBrief, prompt.system)
    return result.model_dump()


def get_content_generator(llm: LLMService | None = None) -> ContentGenerator:
    return ContentGenerator(llm)
