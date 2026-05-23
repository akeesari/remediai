from __future__ import annotations

import re
from pathlib import Path

_DEFAULT_PROMPTS_DIR = Path(__file__).parent.parent.parent / "docs" / "prompts"


class PromptRegistry:
    """Central store for versioned prompt files.

    Prompts live in ``docs/prompts/{name}_v{version}.md``.
    All reads are cached in memory; call ``clear_cache()`` in tests
    that need a clean slate.
    """

    def __init__(self, prompts_dir: Path | None = None) -> None:
        self._dir = prompts_dir or _DEFAULT_PROMPTS_DIR
        self._cache: dict[str, str] = {}

    def load(self, name: str, version: str) -> str:
        """Return the text of prompt *name* at *version* (e.g. ``load("triage", "1")``)."""
        key = f"{name}_v{version}"
        if key not in self._cache:
            path = self._dir / f"{key}.md"
            self._cache[key] = path.read_text(encoding="utf-8")
        return self._cache[key]

    def available_versions(self, name: str) -> list[str]:
        """Return sorted version strings for all ``{name}_vN.md`` files found."""
        pattern = re.compile(rf"^{re.escape(name)}_v(\d+)\.md$")
        versions: list[str] = []
        for p in self._dir.glob(f"{name}_v*.md"):
            m = pattern.match(p.name)
            if m:
                versions.append(m.group(1))
        return sorted(versions, key=int)

    def clear_cache(self) -> None:
        self._cache.clear()


_registry: PromptRegistry | None = None


def get_registry() -> PromptRegistry:
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
    return _registry
