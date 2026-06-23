"""Code analyzer agent tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.agents.code_analyzer_agent import CodeAnalyzerAgent
from backend.models.intelligence import CodeIntelligence, HackathonBrief, RepoContext, RepoFile
from backend.services.github_service import GitHubService


@pytest.fixture
def hackathon_brief(load_fixture):
    return HackathonBrief.model_validate(load_fixture("hackathon_brief.json"))


@pytest.fixture
def mock_repo_context():
    return RepoContext(
        owner="tiangolo",
        repo="fastapi",
        default_branch="master",
        file_tree=["README.md", "fastapi/__init__.py", "pyproject.toml"],
        key_files=[
            RepoFile(path="README.md", content="# FastAPI\n\nFast web framework", size=100),
            RepoFile(path="pyproject.toml", content='[project]\nname = "fastapi"', size=50),
        ],
        languages={"Python": 100000},
        description="FastAPI framework",
        stars=50000,
        forks=5000,
    )


@pytest.mark.asyncio
async def test_code_analyzer_output_schema(mock_gemini, hackathon_brief, mock_repo_context):
    mock_github = MagicMock(spec=GitHubService)
    mock_github.get_repo_context = AsyncMock(return_value=mock_repo_context)

    agent = CodeAnalyzerAgent(gemini=mock_gemini, github=mock_github)
    result = await agent.run(
        "https://github.com/tiangolo/fastapi",
        hackathon_brief.model_dump(),
    )

    assert isinstance(result, CodeIntelligence)
    assert result.project_name
    assert result.confidence_score >= 0.0
    mock_github.get_repo_context.assert_called_once()


@pytest.mark.asyncio
async def test_file_selection_skips_node_modules():
    from backend.services.github_service import _should_skip

    assert _should_skip("node_modules/react/index.js") is True
    assert _should_skip("src/main.py") is False
    assert _should_skip("package-lock.json") is True


@pytest.mark.asyncio
async def test_chunking_large_content():
    from backend.services.github_service import _chunk_content

    lines = [f"line {i}" for i in range(300)]
    content = "\n".join(lines)
    chunked = _chunk_content(content)
    assert "lines omitted" in chunked
    assert "line 0" in chunked
    assert "line 299" in chunked


@pytest.mark.asyncio
async def test_code_analyzer_with_real_repo(mock_gemini, hackathon_brief):
    """Uses real public repo — requires network and GITHUB_TOKEN optional."""
    agent = CodeAnalyzerAgent(gemini=mock_gemini)
    with patch.object(agent.github, "get_repo_context", new_callable=AsyncMock) as mock_ctx:
        mock_ctx.return_value = RepoContext(
            owner="tiangolo",
            repo="fastapi",
            file_tree=["README.md"],
            key_files=[RepoFile(path="README.md", content="# FastAPI", size=10)],
        )
        result = await agent.run(
            "https://github.com/tiangolo/fastapi",
            hackathon_brief,
        )
        assert isinstance(result, CodeIntelligence)
