"""Intelligence models — code analysis, hackathon brief, winner patterns."""

from enum import Enum

from pydantic import BaseModel, Field


class ProjectType(str, Enum):
    WEB_APP = "web_app"
    CLI_TOOL = "cli_tool"
    API = "api"
    LIBRARY = "library"
    ML_MODEL = "ml_model"
    PIPELINE = "pipeline"
    OTHER = "other"


class KeyFeature(BaseModel):
    name: str
    description: str
    technical_detail: str
    hackathon_relevance: str


class Challenge(BaseModel):
    challenge: str
    how_addressed: str


class CodeIntelligence(BaseModel):
    project_name: str
    one_liner: str
    project_type: ProjectType
    primary_language: str
    tech_stack: list[str] = Field(default_factory=list)
    architecture_description: str
    key_features: list[KeyFeature] = Field(default_factory=list)
    novel_approaches: list[str] = Field(default_factory=list)
    real_challenges: list[Challenge] = Field(default_factory=list)
    impressive_code_patterns: list[str] = Field(default_factory=list)
    entry_points: list[str] = Field(default_factory=list)
    api_endpoints: list[str] = Field(default_factory=list)
    external_services_used: list[str] = Field(default_factory=list)
    missing_or_incomplete: list[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)


class JudgingCriterion(BaseModel):
    name: str
    weight: float | int = 0
    description: str = ""


class HackathonBrief(BaseModel):
    event_name: str
    deadline: str = ""
    prize_info: str = ""
    judging_criteria: list[JudgingCriterion] = Field(default_factory=list)
    required_deliverables: list[str] = Field(default_factory=list)
    tracks: list[str] = Field(default_factory=list)
    raw_criteria_text: str = ""


class WinnerSubmission(BaseModel):
    project_name: str = ""
    tagline: str = ""
    what_it_does_opening: str = ""
    built_with: list[str] = Field(default_factory=list)
    word_counts: dict[str, int] = Field(default_factory=dict)


class WinnerPatterns(BaseModel):
    hackathon_name: str = ""
    submissions_analyzed: int = 0
    tagline_patterns: list[str] = Field(default_factory=list)
    opening_sentence_patterns: list[str] = Field(default_factory=list)
    common_tech_stacks: list[str] = Field(default_factory=list)
    average_word_counts: dict[str, int] = Field(default_factory=dict)
    framing_recommendations: list[str] = Field(default_factory=list)
    submissions: list[WinnerSubmission] = Field(default_factory=list)


class WinningBrief(BaseModel):
    headline_recommendation: str
    top_criteria_to_address: list[str] = Field(default_factory=list)
    vocabulary_to_use: list[str] = Field(default_factory=list)
    vocabulary_to_avoid: list[str] = Field(default_factory=list)
    winning_patterns_observed: list[str] = Field(default_factory=list)
    recommended_word_counts: dict[str, int] = Field(default_factory=dict)
    content_angle: str = ""


class RepoFile(BaseModel):
    path: str
    content: str
    size: int = 0


class RepoContext(BaseModel):
    owner: str
    repo: str
    default_branch: str = "main"
    file_tree: list[str] = Field(default_factory=list)
    key_files: list[RepoFile] = Field(default_factory=list)
    languages: dict[str, int] = Field(default_factory=dict)
    description: str = ""
    stars: int = 0
    forks: int = 0
