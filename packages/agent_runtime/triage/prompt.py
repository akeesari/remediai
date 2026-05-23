from pathlib import Path

_PROMPT_DIR = Path(__file__).parent.parent.parent.parent / "docs" / "prompts"
_CACHE: dict[str, str] = {}


def load_triage_prompt() -> str:
    """Load and cache the triage_v1 prompt from docs/prompts/triage_v1.md."""
    key = "triage_v1"
    if key not in _CACHE:
        _CACHE[key] = (_PROMPT_DIR / "triage_v1.md").read_text(encoding="utf-8")
    return _CACHE[key]
