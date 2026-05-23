from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class RootCauseJson(BaseModel):
    component: str
    likely_cause: str
    contributing_factors: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5)

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


class RootCauseOutput(BaseModel):
    root_cause_summary: str
    root_cause_json: RootCauseJson
    evidence: list[str] = Field(default_factory=list)
