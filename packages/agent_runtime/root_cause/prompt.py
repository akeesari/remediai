from __future__ import annotations

from pathlib import Path

_PROMPT_DIR = Path(__file__).parent.parent.parent.parent / "docs" / "prompts"
_CACHE: dict[str, str] = {}


def load_root_cause_prompt() -> str:
    key = "root_cause_v1"
    if key not in _CACHE:
        _CACHE[key] = (_PROMPT_DIR / "root_cause_v1.md").read_text(encoding="utf-8")
    return _CACHE[key]
