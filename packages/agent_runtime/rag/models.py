from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class RAGResult(BaseModel):
    source: str
    title: str
    excerpt: str
    relevance_score: float = Field(default=0.0)
    url: str | None = None

    @field_validator("relevance_score")
    @classmethod
    def clamp_score(cls, v: float) -> float:
        return max(0.0, float(v))
