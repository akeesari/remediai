from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Recommendation(BaseModel):
    rank: int
    title: str
    description: str
    affected_files: list[str] = Field(default_factory=list)
    suggested_change: str
    confidence: float = Field(default=0.5)
    source_refs: list[str] = Field(default_factory=list)

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


class FixPlannerOutput(BaseModel):
    recommendations: list[Recommendation]
