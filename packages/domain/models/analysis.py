from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class CodeSnippet(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    content: str
    repo: str
    commit_sha: str


class RAGResult(BaseModel):
    source: str
    title: str
    excerpt: str
    relevance_score: float
    url: str | None = None


class RootCauseJson(BaseModel):
    component: str
    likely_cause: str
    contributing_factors: list[str]
    confidence: float


class Recommendation(BaseModel):
    rank: int
    title: str
    description: str
    affected_files: list[str]
    suggested_change: str
    confidence: float
    source_refs: list[str] = Field(default_factory=list)


class IncidentAnalysis(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    root_cause: str | None = None
    root_cause_json: RootCauseJson | None = None
    recommendations: list[Recommendation] = Field(default_factory=list)
    code_snippets: list[CodeSnippet] = Field(default_factory=list)
    rag_results: list[RAGResult] = Field(default_factory=list)
    agent_trace: list["AgentTraceEntry"] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


from packages.domain.models.audit import AgentTraceEntry  # noqa: E402

IncidentAnalysis.model_rebuild()
