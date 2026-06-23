"""Pytest fixtures — in-memory store, mocked Gemini, test client."""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from backend.api.deps import get_store
from backend.config import get_settings
from backend.main import app
from backend.models.artifact import Artifact, ArtifactStatus, ArtifactType, Revision
from backend.models.content import ArtifactScore
from backend.models.intelligence import (
    CodeIntelligence,
    HackathonBrief,
    WinnerPatterns,
    WinningBrief,
)
from backend.models.metric import Metric, Retrospective
from backend.models.run import IntakeData, Run, RunStatus
from httpx import ASGITransport, AsyncClient

FIXTURES = Path(__file__).parent / "fixtures"

TEST_API_SECRET = "test-secret-for-pytest-only"


@pytest.fixture(autouse=True)
def _test_api_secret(monkeypatch):
    """Use a fixed test secret — never read real credentials from .env in tests."""
    monkeypatch.setenv("LAUNCHKIT_API_SECRET", TEST_API_SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class InMemoryArtifactStore:
    """In-memory artifact store for tests (no Supabase required)."""

    def __init__(self) -> None:
        self.runs: dict[UUID, dict] = {}
        self.artifacts: dict[tuple[UUID, str], dict] = {}
        self.revisions: list[dict] = []
        self.metrics: list[dict] = []
        self.retrospectives: dict[UUID, dict] = {}

    async def create_run(self, intake_data: IntakeData) -> Run:
        run_id = uuid4()
        now = datetime.now(UTC)
        row = {
            "id": str(run_id),
            "status": RunStatus.INTAKE.value,
            "intake": intake_data.model_dump(),
            "hackathon_brief": None,
            "winner_patterns": None,
            "winning_brief": None,
            "repo_context": None,
            "code_intelligence": None,
            "quality_report": None,
            "publishing_results": {},
            "analytics": {},
            "error_message": None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        self.runs[run_id] = row
        return self._parse_run(row)

    async def get_run(self, run_id: UUID) -> Run:
        if run_id not in self.runs:
            from backend.core.exceptions import NotFoundError

            raise NotFoundError(f"Run {run_id} not found", f"No run with id {run_id}")
        return self._parse_run(self.runs[run_id])

    async def update_run_status(self, run_id: UUID, status: RunStatus) -> Run:
        return await self.update_run(run_id, {"status": status.value})

    async def update_run(self, run_id: UUID, fields: dict) -> Run:
        if run_id not in self.runs:
            from backend.core.exceptions import NotFoundError

            raise NotFoundError(f"Run {run_id} not found", f"No run with id {run_id}")
        self.runs[run_id].update(fields)
        self.runs[run_id]["updated_at"] = datetime.now(UTC).isoformat()
        return self._parse_run(self.runs[run_id])

    async def upsert_artifact(
        self,
        run_id,
        artifact_type,
        content,
        status=ArtifactStatus.GENERATED,
        quality_score=None,
        quality_feedback=None,
    ) -> Artifact:
        atype = artifact_type.value if isinstance(artifact_type, ArtifactType) else artifact_type
        astatus = status.value if isinstance(status, ArtifactStatus) else status
        key = (run_id, atype)
        now = datetime.now(UTC)
        if key in self.artifacts:
            self.artifacts[key].update(
                {
                    "content": content,
                    "status": astatus,
                    "quality_score": quality_score,
                    "quality_feedback": quality_feedback,
                    "updated_at": now.isoformat(),
                }
            )
        else:
            self.artifacts[key] = {
                "id": str(uuid4()),
                "run_id": str(run_id),
                "artifact_type": atype,
                "content": content,
                "status": astatus,
                "quality_score": quality_score,
                "quality_feedback": quality_feedback,
                "published_url": None,
                "revision_count": 0,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        return self._parse_artifact(self.artifacts[key])

    async def get_artifact(self, run_id, artifact_type) -> Artifact:
        atype = artifact_type.value if isinstance(artifact_type, ArtifactType) else artifact_type
        key = (run_id, atype)
        if key not in self.artifacts:
            from backend.core.exceptions import NotFoundError

            raise NotFoundError(f"Artifact {atype} not found", f"No {atype} for run {run_id}")
        return self._parse_artifact(self.artifacts[key])

    async def list_artifacts(self, run_id: UUID) -> list[Artifact]:
        return [self._parse_artifact(a) for (rid, _), a in self.artifacts.items() if rid == run_id]

    async def approve_artifact(self, run_id, artifact_type) -> Artifact:
        atype = artifact_type.value if isinstance(artifact_type, ArtifactType) else artifact_type
        key = (run_id, atype)
        self.artifacts[key]["status"] = ArtifactStatus.APPROVED.value
        return self._parse_artifact(self.artifacts[key])

    async def create_revision(
        self,
        run_id,
        artifact_type,
        feedback,
        previous_content,
        new_content,
    ) -> Revision:
        atype = artifact_type.value if isinstance(artifact_type, ArtifactType) else artifact_type
        key = (run_id, atype)
        self.artifacts[key]["content"] = new_content
        self.artifacts[key]["revision_count"] = self.artifacts[key].get("revision_count", 0) + 1
        rev = {
            "id": str(uuid4()),
            "run_id": str(run_id),
            "artifact_type": atype,
            "feedback": feedback,
            "previous_content": previous_content,
            "new_content": new_content,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self.revisions.append(rev)
        return Revision(
            id=UUID(rev["id"]),
            run_id=run_id,
            artifact_type=ArtifactType(atype),
            feedback=feedback,
            previous_content=previous_content,
            new_content=new_content,
            created_at=datetime.now(UTC),
        )

    async def record_metric(self, run_id, source, metric_type, value, delta=None) -> Metric:
        row = {
            "id": str(uuid4()),
            "run_id": str(run_id),
            "source": source,
            "metric_type": metric_type,
            "value": value,
            "delta": delta,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        self.metrics.append(row)
        return Metric(
            id=UUID(row["id"]),
            run_id=run_id,
            source=source,
            metric_type=metric_type,
            value=value,
            delta=delta,
            recorded_at=datetime.now(UTC),
        )

    async def get_metrics(self, run_id: UUID) -> list[Metric]:
        return [
            Metric(
                id=UUID(m["id"]),
                run_id=run_id,
                source=m["source"],
                metric_type=m["metric_type"],
                value=m["value"],
                delta=m.get("delta"),
                recorded_at=datetime.fromisoformat(m["recorded_at"]),
            )
            for m in self.metrics
            if UUID(m["run_id"]) == run_id
        ]

    async def save_retrospective(self, run_id: UUID, content: str) -> Retrospective:
        now = datetime.now(UTC)
        self.retrospectives[run_id] = {
            "id": str(uuid4()),
            "run_id": str(run_id),
            "content": content,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        r = self.retrospectives[run_id]
        return Retrospective(
            id=UUID(r["id"]),
            run_id=run_id,
            content=content,
            created_at=now,
            updated_at=now,
        )

    async def get_retrospective(self, run_id: UUID) -> Retrospective | None:
        if run_id not in self.retrospectives:
            return None
        r = self.retrospectives[run_id]
        return Retrospective(
            id=UUID(r["id"]),
            run_id=run_id,
            content=r["content"],
            created_at=datetime.fromisoformat(r["created_at"]),
            updated_at=datetime.fromisoformat(r["updated_at"]),
        )

    def _parse_run(self, row: dict) -> Run:
        from backend.models.run import AnalyticsSnapshot, PublishingResults

        return Run(
            id=UUID(row["id"]),
            status=RunStatus(row["status"]),
            intake=IntakeData(**row["intake"]),
            hackathon_brief=row.get("hackathon_brief"),
            winner_patterns=row.get("winner_patterns"),
            winning_brief=row.get("winning_brief"),
            repo_context=row.get("repo_context"),
            code_intelligence=row.get("code_intelligence"),
            quality_report=row.get("quality_report"),
            publishing_results=PublishingResults(**(row.get("publishing_results") or {})),
            analytics=AnalyticsSnapshot(**(row.get("analytics") or {})),
            error_message=row.get("error_message"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _parse_artifact(self, row: dict) -> Artifact:
        return Artifact(
            id=UUID(row["id"]),
            run_id=UUID(row["run_id"]),
            artifact_type=ArtifactType(row["artifact_type"]),
            status=ArtifactStatus(row["status"]),
            content=row.get("content"),
            quality_score=row.get("quality_score"),
            quality_feedback=row.get("quality_feedback"),
            published_url=row.get("published_url"),
            revision_count=row.get("revision_count", 0),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


@pytest.fixture
def memory_store():
    return InMemoryArtifactStore()


@pytest.fixture
async def test_client(memory_store):
    app.dependency_overrides[get_store] = lambda: memory_store
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {TEST_API_SECRET}"}


@pytest.fixture
def load_fixture():
    def _load(name: str) -> dict:
        return json.loads((FIXTURES / name).read_text())

    return _load


@pytest.fixture
def sample_hackathon_brief(load_fixture) -> HackathonBrief:
    return HackathonBrief.model_validate(load_fixture("hackathon_brief.json"))


@pytest.fixture
def sample_code_intelligence(load_fixture) -> CodeIntelligence:
    return CodeIntelligence.model_validate(load_fixture("code_intelligence.json"))


@pytest.fixture
def sample_run(memory_store, sample_hackathon_brief) -> Run:
    """Pre-populated run — use via async fixture in tests that need it."""
    import asyncio

    async def _create():
        run = await memory_store.create_run(
            IntakeData(
                github_url="https://github.com/tiangolo/fastapi",
                hackathon_url="https://devpost.com/hackathons",
                hackathon_name="Test Hackathon",
            )
        )
        await memory_store.update_run(
            run.id,
            {
                "hackathon_brief": sample_hackathon_brief.model_dump(),
                "status": RunStatus.INTAKE.value,
            },
        )
        return await memory_store.get_run(run.id)

    return asyncio.get_event_loop().run_until_complete(_create())


class MockLLMService:
    """Returns fixture data instead of calling an LLM API."""

    async def generate_text(
        self, prompt: str, system_prompt: str | None = None, temperature: float = 0.7
    ) -> str:
        return "# Mock README\n\nGenerated content for testing."

    async def generate_structured(
        self, prompt: str, output_schema, system_prompt: str | None = None, temperature: float = 0.3
    ):
        name = output_schema.__name__
        if name == "CodeIntelligence":
            data = json.loads((FIXTURES / "code_intelligence.json").read_text())
            return CodeIntelligence.model_validate(data)
        if name == "HackathonBrief":
            data = json.loads((FIXTURES / "hackathon_brief.json").read_text())
            return HackathonBrief.model_validate(data)
        if name == "WinnerPatterns":
            return WinnerPatterns(hackathon_name="Test", submissions_analyzed=0)
        if name == "WinningBrief":
            return WinningBrief(headline_recommendation="Lead with orchestration")
        if name == "ArtifactScore":
            bad_phrases = ("generic", "lorem ipsum", "helps users", "simple basic", "basic wrapper")
            is_bad = any(phrase in prompt.lower() for phrase in bad_phrases)
            score = 4.0 if is_bad else 8.5
            return ArtifactScore(
                overall_score=score,
                scores={
                    "criterion_alignment": score,
                    "specificity": score,
                    "readability": score,
                    "tone": score,
                },
                top_improvement="Add more specifics" if is_bad else "Looks good",
                flag_for_auto_revision=score < 6.5,
            )
        if name == "DevpostCopy":
            data = json.loads((FIXTURES / "devpost_copy.json").read_text())
            from backend.models.content import DevpostCopy

            return DevpostCopy.model_validate(data)
        if name == "DemoScript":
            from backend.models.content import DemoScript, DemoSegment

            return DemoScript(
                segments=[
                    DemoSegment(
                        timestamp_start="0:00",
                        timestamp_end="1:00",
                        title="Intro",
                        narration="Hello",
                        screen_action="Show app",
                        key_point="Problem",
                    )
                ]
            )
        if name == "SocialContent":
            from backend.models.content import SocialContent

            return SocialContent(linkedin_post="Mock post", hashtags=["hackathon"])
        return output_schema.model_validate({})


@pytest.fixture
def mock_llm():
    return MockLLMService()


@pytest.fixture
def mock_gemini(mock_llm):
    """Backward-compatible alias."""
    return mock_llm
