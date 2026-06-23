"""
Code Analysis Agent.

Reads a GitHub repository, selects key source files, and produces
structured CodeIntelligence via Gemini.

Inputs: github_url (str), hackathon_brief (dict)
Outputs: CodeIntelligence
"""

import json
import logging

from backend.core.exceptions import AgentError, ValidationError
from backend.models.intelligence import CodeIntelligence, HackathonBrief
from backend.services.github_service import GitHubService, get_github_service
from backend.services.llm_service import LLMService, get_llm_service
from backend.services.prompt_loader import load_prompt

logger = logging.getLogger("launchkit.agent.code")


class CodeAnalyzerAgent:
    """Analyze GitHub repo and produce hackathon-aware code intelligence."""

    def __init__(
        self,
        llm: LLMService | None = None,
        gemini: LLMService | None = None,
        github: GitHubService | None = None,
    ) -> None:
        self.llm = llm or gemini or get_llm_service()
        self.github = github or get_github_service()

    async def run(
        self,
        github_url: str,
        hackathon_brief: dict | HackathonBrief,
    ) -> CodeIntelligence:
        if not github_url:
            raise ValidationError("github_url is required", "Provide a valid GitHub repository URL")

        if isinstance(hackathon_brief, HackathonBrief):
            brief = hackathon_brief
        else:
            brief = HackathonBrief.model_validate(hackathon_brief)

        try:
            repo_context = await self.github.get_repo_context(github_url)
        except Exception as exc:
            raise AgentError("Failed to fetch repository", str(exc)) from exc

        criteria_summary = json.dumps(
            [c.model_dump() for c in brief.judging_criteria],
            indent=2,
        )
        file_tree = "\n".join(repo_context.file_tree[:200])
        key_contents = "\n\n---\n\n".join(
            f"### {f.path}\n```\n{f.content}\n```" for f in repo_context.key_files
        )

        prompt = load_prompt("code_analysis")
        user_prompt = prompt.render_user(
            file_tree=file_tree,
            key_file_contents=key_contents,
            hackathon_criteria_summary=criteria_summary,
        )

        try:
            return await self.llm.generate_structured(
                prompt=user_prompt,
                output_schema=CodeIntelligence,
                system_prompt=prompt.system,
            )
        except Exception as exc:
            raise AgentError("Code analysis failed", str(exc)) from exc

    async def run_with_context(
        self,
        github_url: str,
        hackathon_brief: dict | HackathonBrief,
    ) -> tuple[CodeIntelligence, dict]:
        """Run analysis and return both CodeIntelligence and repo_context dict."""
        from backend.services.github_service import get_github_service

        github = self.github or get_github_service()
        repo_context = await github.get_repo_context(github_url)
        intel = await self.run(github_url, hackathon_brief)
        return intel, repo_context.model_dump()
