from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ValidationCheck(BaseModel):
    check_name: str
    status: Literal["pass", "warn", "fail"]
    detail: str


class ValidationReport(BaseModel):
    overall_status: Literal["approved", "needs_review", "blocked"]
    checks: list[ValidationCheck] = Field(default_factory=list)
    llm_assessment: str
    risk_level: Literal["low", "medium", "high"]
    confidence: float
    reviewer_notes: str
