from __future__ import annotations

from pydantic import BaseModel


class BugCreationResult(BaseModel):
    bug_id: int
    bug_url: str
    title: str
