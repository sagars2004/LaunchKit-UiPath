"""
Quality Scorer Agent.

Scores each submission artifact against hackathon judging criteria.
Runs 5 concurrent Gemini calls (one per artifact).

Inputs: artifacts dict (type → content string), hackathon_brief (dict)
Outputs: QualityReport
"""

import asyncio
import json
import logging

from backend.core.exceptions import ValidationError
from backend.models.artifact import ArtifactType
from backend.models.content import ArtifactScore, QualityReport
from backend.models.intelligence import HackathonBrief
from backend.services.llm_service import LLMService, get_llm_service
from backend.services.prompt_loader import load_prompt

logger = logging.getLogger("launchkit.agent.quality")

AUTO_REVISION_THRESHOLD = 6.5
ARTIFACT_TYPES = [t.value for t in ArtifactType]


class QualityScorerAgent:
    """Score submission artifacts against hackathon judging criteria."""

    def __init__(self, llm: LLMService | None = None, gemini: LLMService | None = None) -> None:
        self.llm = llm or gemini or get_llm_service()

    async def run(
        self,
        artifacts: dict[str, str],
        hackathon_brief: dict | HackathonBrief,
    ) -> QualityReport:
        if not artifacts:
            raise ValidationError("No artifacts to score", "artifacts dict is empty")

        if isinstance(hackathon_brief, HackathonBrief):
            brief = hackathon_brief
        else:
            brief = HackathonBrief.model_validate(hackathon_brief)

        judging_criteria = json.dumps(
            [c.model_dump() for c in brief.judging_criteria],
            indent=2,
        )

        tasks = [
            self._score_one(artifact_type, content, judging_criteria)
            for artifact_type, content in artifacts.items()
            if content
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        report = QualityReport()

        for artifact_type, result in zip(
            [k for k, v in artifacts.items() if v], results, strict=True
        ):
            if isinstance(result, Exception):
                logger.error("Scoring failed for %s: %s", artifact_type, result)
                report.artifacts[artifact_type] = ArtifactScore(
                    overall_score=0.0,
                    top_improvement=f"Scoring failed: {result}",
                    flag_for_auto_revision=True,
                )
            else:
                if result.overall_score < AUTO_REVISION_THRESHOLD:
                    result.flag_for_auto_revision = True
                report.artifacts[artifact_type] = result

        return report

    async def _score_one(
        self,
        artifact_type: str,
        content: str,
        judging_criteria: str,
    ) -> ArtifactScore:
        prompt = load_prompt("quality_scoring")
        user_prompt = prompt.render_user(
            artifact_type=artifact_type,
            artifact_content=content[:8000],
            judging_criteria=judging_criteria,
        )
        return await self.llm.generate_structured(
            prompt=user_prompt,
            output_schema=ArtifactScore,
            system_prompt=prompt.system,
        )
