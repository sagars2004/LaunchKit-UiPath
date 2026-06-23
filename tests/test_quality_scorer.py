"""Quality scorer agent tests."""

import pytest
from backend.agents.quality_scorer_agent import AUTO_REVISION_THRESHOLD, QualityScorerAgent
from backend.models.content import QualityReport


@pytest.fixture
def hackathon_brief(load_fixture):
    return load_fixture("hackathon_brief.json")


@pytest.mark.asyncio
async def test_score_bad_content_flags_revision(mock_gemini, hackathon_brief):
    agent = QualityScorerAgent(gemini=mock_gemini)
    artifacts = {
        "readme": "I built a web app that helps users do generic things with lorem ipsum.",
        "devpost_copy": "This solution helps users. It is a simple basic wrapper.",
    }
    report = await agent.run(artifacts, hackathon_brief)
    assert isinstance(report, QualityReport)
    for score in report.artifacts.values():
        assert score.overall_score < AUTO_REVISION_THRESHOLD
        assert score.flag_for_auto_revision is True


@pytest.mark.asyncio
async def test_score_good_content_high_scores(mock_gemini, hackathon_brief):
    agent = QualityScorerAgent(gemini=mock_gemini)
    artifacts = {
        "readme": (
            "LaunchKit orchestrates a Maestro BPMN pipeline that reduces submission "
            "packaging from 3 hours to 20 minutes using Gemini 2.0 Flash coded agents."
        ),
    }
    report = await agent.run(artifacts, hackathon_brief)
    score = report.artifacts["readme"]
    assert score.overall_score >= AUTO_REVISION_THRESHOLD
    assert score.flag_for_auto_revision is False


@pytest.mark.asyncio
async def test_auto_revision_threshold():
    assert AUTO_REVISION_THRESHOLD == 6.5
