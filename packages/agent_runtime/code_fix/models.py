from __future__ import annotations

from pydantic import BaseModel, field_validator


class CodeFixResult(BaseModel):
    file_path: str
    original_content: str
    patched_content: str
    change_summary: str
    confidence: float
    patch_applied: bool

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))
