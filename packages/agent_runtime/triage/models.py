from pydantic import BaseModel, Field, field_validator

_VALID_PRIORITIES = {"critical", "high", "medium", "low"}


class TriageOutput(BaseModel):
    priority: str
    triage_labels: list[str]
    group_id: str | None = None
    rationale: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("priority")
    @classmethod
    def normalise_priority(cls, v: str) -> str:
        v = v.lower().strip()
        return v if v in _VALID_PRIORITIES else "medium"

    @field_validator("triage_labels")
    @classmethod
    def ensure_non_empty_labels(cls, v: list[str]) -> list[str]:
        return v if v else ["unknown"]
