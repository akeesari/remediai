from __future__ import annotations

from pydantic import BaseModel, Field


class PRAgentOutput(BaseModel):
    pr_branch: str
    pr_url: str
    pr_id: int
    patch_applied: bool
    files_changed: list[str] = Field(default_factory=list)
